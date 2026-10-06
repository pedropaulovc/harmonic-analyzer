"""Read exact archived CAD sources through the authoritative identity map.

The map resolves logical current filenames to original released filenames. It
never edits the archive, rewrites imports, or installs legacy runtime aliases.
Native node-path projection is exclusively performed by native-identity-map.mjs.
"""
from __future__ import annotations

import ast
import operator
import hashlib
import importlib
import json
import re
import subprocess
import struct
from pathlib import Path, PurePosixPath


MAP_SHA256 = "1ee9084204cab7025783c5bf0fa98e040cfaa3e4e8200f0d61e58e8dd32c3bfd"
RELEASE_MODELS = {
    "1268c23d4a8fc741147c5e09d8d1e45247a71945":
        "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d",
    "81539e53f5146c06a77541415bd79da673806d96":
        "60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c",
}


def glb_nodes(path: Path) -> tuple[dict[str, list[float]], str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        stream.seek(0)
        magic, version, size = struct.unpack("<III", stream.read(12))
        if magic != 0x46546C67 or version != 2 or size != path.stat().st_size:
            raise ValueError("Not a complete GLB 2 file")
        length, kind = struct.unpack("<II", stream.read(8))
        if kind != 0x4E4F534A:
            raise ValueError("The first GLB chunk must be JSON")
        gltf = json.loads(stream.read(length))
    identity = [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    result: dict[str, list[float]] = {}

    def multiply(a: list[float], b: list[float]) -> list[float]:
        return [
            sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
            for col in range(4)
            for row in range(4)
        ]

    def visit(index: int, parent: list[float], prefix: str) -> None:
        node = gltf["nodes"][index]
        name = node.get("name", f"unnamed-{index}")
        fullpath = f"{prefix}/{name}" if prefix else name
        if "matrix" in node:
            local = node["matrix"]
        else:
            x, y, z, w = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
            sx, sy, sz = node.get("scale", [1.0, 1.0, 1.0])
            tx, ty, tz = node.get("translation", [0.0, 0.0, 0.0])
            local = [
                (1 - 2 * (y * y + z * z)) * sx,
                2 * (x * y + z * w) * sx,
                2 * (x * z - y * w) * sx,
                0.0,
                2 * (x * y - z * w) * sy,
                (1 - 2 * (x * x + z * z)) * sy,
                2 * (y * z + x * w) * sy,
                0.0,
                2 * (x * z + y * w) * sz,
                2 * (y * z - x * w) * sz,
                (1 - 2 * (x * x + y * y)) * sz,
                0.0,
                tx,
                ty,
                tz,
                1.0,
            ]
        world = multiply(parent, local)
        if fullpath in result:
            raise ValueError(f"Duplicate qualified model path: {fullpath}")
        result[fullpath] = world
        for child in node.get("children", []):
            visit(child, world, fullpath)

    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visit(root, identity, "")
    return result, digest.hexdigest()


def validate_release_pair(source_commit: str, raw_sha256: str) -> None:
    """Do not permit an established release identity to acquire other bytes."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("--source-commit must be exactly 40 lowercase hexadecimal characters")
    if not re.fullmatch(r"[0-9a-f]{64}", raw_sha256):
        raise ValueError("--expected-model-sha256 must be exactly 64 lowercase hexadecimal characters")
    if source_commit in RELEASE_MODELS and RELEASE_MODELS[source_commit] != raw_sha256:
        raise ValueError(
            f"--source-commit {source_commit} requires the existing raw model SHA256 "
            f"{RELEASE_MODELS[source_commit]}; its native release pin cannot be replaced"
        )
    for commit, digest in RELEASE_MODELS.items():
        if digest == raw_sha256 and commit != source_commit:
            raise ValueError(f"Raw model SHA256 {digest} requires its exact source commit {commit}")


class CadIdentityMap:
    def __init__(self, repo: Path):
        path = repo / "cad/config/identity-migration-map.json"
        raw = path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        if self.sha256 != MAP_SHA256:
            raise ValueError(f"CAD identity map SHA256 {self.sha256} differs from pinned {MAP_SHA256}")
        mapping = json.loads(raw)
        if mapping.get("schema_version") != 2 or len(mapping.get("identities", [])) != 154:
            raise ValueError("CAD identity map must contain the complete schema-v2 identity inventory")
        renames = mapping.get("file_renames")
        if not isinstance(renames, dict) or not renames:
            raise ValueError("CAD identity map lacks its file_renames authority")
        if len(set(renames.values())) != len(renames):
            raise ValueError("CAD identity file renames must be bijective")
        for old, new in renames.items():
            for relative in (old, new):
                if not isinstance(relative, str):
                    raise ValueError("CAD identity file paths must be strings")
                parsed = PurePosixPath(relative)
                if (parsed.is_absolute() or ".." in parsed.parts
                        or parsed.as_posix() != relative or not relative.startswith("cad/")):
                    raise ValueError(f"Unsafe CAD identity file path: {relative}")
        self.original_paths = {new: old for old, new in renames.items()}

    def source_file(self, cad: Path, logical_relative: str) -> Path:
        """Select exactly one map-declared filename inside the archived CAD tree."""
        logical = PurePosixPath(logical_relative)
        if logical.is_absolute() or ".." in logical.parts or logical.as_posix() != logical_relative:
            raise ValueError(f"Unsafe logical CAD source path: {logical_relative}")
        canonical = "cad/" + logical_relative
        original = self.original_paths.get(canonical, canonical)
        candidates = [cad.parent / original]
        if canonical != original:
            candidates.append(cad.parent / canonical)
        present = [path for path in candidates if path.is_file()]
        if len(present) != 1:
            reason = "Ambiguous" if present else "Missing"
            raise ValueError(f"{reason} archived CAD source for {canonical}: {original}")
        path = present[0]
        if not path.resolve().is_relative_to(cad.resolve()):
            raise ValueError(f"Archived CAD source escapes snapshot: {path}")
        return path

    def import_module(self, cad: Path, logical_name: str):
        path = self.source_file(cad, f"scripts/{logical_name}.py")
        module = importlib.import_module(path.stem)
        if not getattr(module, "__file__", None) or Path(module.__file__).resolve() != path.resolve():
            raise ValueError(f"CAD module {path.stem} was not imported from the exact archived source {path}")
        return module

    def registry_name(self, cad: Path, logical_stem: str) -> str:
        return self.source_file(cad, f"config/parts/{logical_stem}.yaml").stem


def magnifier_installation(path: Path) -> dict[str, float]:
    """Read numeric datums; refuse unsupported module-scope writes, never guess."""
    tree = ast.parse(path.read_text(), filename=str(path))
    assignments = {}
    unsupported = set()

    class Bindings(ast.NodeVisitor):
        def __init__(self, global_names=None):
            self.global_names = global_names

        def bind(self, name):
            if self.global_names is None or name in self.global_names:
                unsupported.add(name)

        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.bind(node.id)

        def visit_FunctionDef(self, node):
            self.bind(node.name)
            for expression in (*node.decorator_list, *node.args.defaults,
                               *[value for value in node.args.kw_defaults if value is not None]):
                self.visit(expression)
            self.visit_scope_body(node.body)

        def visit_scope_body(self, body):
            # Local writes are not assembly datums. Explicit global writes are.
            global_names = set()

            class Globals(ast.NodeVisitor):
                def visit_Global(self, declaration):
                    global_names.update(declaration.names)

                def visit_FunctionDef(self, declaration):
                    pass

                visit_AsyncFunctionDef = visit_FunctionDef
                visit_ClassDef = visit_FunctionDef
                visit_Lambda = visit_FunctionDef

            declarations = Globals()
            for statement in body:
                declarations.visit(statement)
            bindings = Bindings(global_names)
            for statement in body:
                bindings.visit(statement)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            self.bind(node.name)
            for expression in (*node.decorator_list, *node.bases,
                               *[keyword.value for keyword in node.keywords]):
                self.visit(expression)
            self.visit_scope_body(node.body)

        def visit_Lambda(self, node):
            for expression in (*node.args.defaults,
                               *[value for value in node.args.kw_defaults if value is not None]):
                self.visit(expression)

        def visit_Import(self, node):
            for alias in node.names:
                self.bind(alias.asname or alias.name.split(".")[0])

        def visit_ImportFrom(self, node):
            for alias in node.names:
                self.bind(alias.asname or alias.name)

        def visit_ExceptHandler(self, node):
            if node.name:
                self.bind(node.name)
            self.generic_visit(node)

        def visit_ListComp(self, node):
            # Comprehension targets have their own scope; walrus writes do not.
            for generator in node.generators:
                self.visit(generator.iter)
                for condition in generator.ifs:
                    self.visit(condition)
            if isinstance(node, ast.DictComp):
                self.visit(node.key)
                self.visit(node.value)
            else:
                self.visit(node.elt)

        visit_SetComp = visit_ListComp
        visit_DictComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

        def visit_MatchAs(self, node):
            if node.name:
                self.bind(node.name)
            self.generic_visit(node)

        visit_MatchStar = visit_MatchAs

        def visit_MatchMapping(self, node):
            if node.rest:
                self.bind(node.rest)
            self.generic_visit(node)

    bindings = Bindings()
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and all(
            isinstance(target, ast.Name) for target in statement.targets
        ):
            for target in statement.targets:
                assignments.setdefault(target.id, []).append(statement.value)
            bindings.visit(statement.value)
        else:
            bindings.visit(statement)
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def number(node, active: frozenset[str]) -> float:
        if isinstance(node, ast.Constant) and type(node.value) in (float, int):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id not in active and node.id not in unsupported:
            expressions = assignments.get(node.id, [])
            if len(expressions) == 1:
                return number(expressions[0], active | {node.id})
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = number(node.operand, active)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](number(node.left, active), number(node.right, active))
        raise ValueError(f"Missing, ambiguous or nonnumeric magnifier installation datum in {path}")

    return {
        name: number(ast.Name(id=name, ctx=ast.Load()), frozenset())
        for name in ("LEVER_ROD_Y", "LEVER_ROD_Z", "VROD_TOP_Y", "FIXTURE_Y0")
    }


def validate_path_projection(raw_nodes: dict, raw_sha256: str, projection: dict,
                             identity_map: CadIdentityMap) -> tuple[dict, dict]:
    """Validate the CLI association and a complete bijection before using keys."""
    if not isinstance(projection, dict) or projection.get("rawSha256") != raw_sha256:
        raise ValueError("Native identity projection is not bound to the approved original raw model")
    identity = projection.get("identity")
    if not isinstance(identity, dict) or identity.get("mapSha256") != identity_map.sha256:
        raise ValueError("Native identity projection does not use the pinned CAD identity map")
    if not re.fullmatch(r"[0-9a-f]{64}", str(identity.get("canonicalSha256", ""))):
        raise ValueError("Native identity projection lacks its canonical model SHA256")
    for field in ("nodeCount", "renamedNodes"):
        if type(identity.get(field)) is not int or identity[field] < 0:
            raise ValueError(f"Native identity projection has invalid {field}")
    rows = projection.get("paths")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Native identity projection has no complete native path inventory")
    sources, targets = set(), set()
    canonical_nodes = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid native identity projection path record")
        source, canonical = row.get("source"), row.get("canonical")
        if not isinstance(source, str) or not isinstance(canonical, str):
            raise ValueError("Native identity projection paths must be strings")
        if source in sources or canonical in targets:
            raise ValueError("Native identity projection paths must be bijective")
        if source not in raw_nodes:
            raise ValueError(f"Native identity projection has unknown raw path: {source}")
        if canonical != "ha-harmonic-analyzer" and not canonical.startswith("ha-harmonic-analyzer/"):
            raise ValueError(f"Native identity projection has noncanonical native path: {canonical}")
        sources.add(source)
        targets.add(canonical)
        canonical_nodes[canonical] = raw_nodes[source]
    native_sources = {
        path for path in raw_nodes
        if path in ("harmonic-analyzer", "ha-harmonic-analyzer")
        or path.startswith(("harmonic-analyzer/", "ha-harmonic-analyzer/"))
    }
    if sources != native_sources:
        raise ValueError("Native identity projection must cover every raw native node exactly once")
    if identity["nodeCount"] < len(raw_nodes) or identity["renamedNodes"] > len(sources):
        raise ValueError("Native identity projection node counts disagree with raw inventory")
    for path, matrix in raw_nodes.items():
        if path not in sources:
            if path in canonical_nodes:
                raise ValueError(f"Native identity projection collides with untouched model path: {path}")
            canonical_nodes[path] = matrix
    return canonical_nodes, identity


def project_model_paths(model: Path, raw_nodes: dict, raw_sha256: str,
                        identity_map: CadIdentityMap) -> tuple[dict, dict]:
    helper = Path(__file__).with_name("native-identity-map.mjs")
    try:
        result = subprocess.check_output(
            ["node", str(helper), "--model", str(model.resolve()), "--paths-only"],
            text=True, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Native identity projection refused the raw model: {error.stderr.strip()}") from error
    return validate_path_projection(raw_nodes, raw_sha256, json.loads(result), identity_map)
