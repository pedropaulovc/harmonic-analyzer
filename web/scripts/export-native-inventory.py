#!/usr/bin/env python3
"""Export approved native rest matrices for fit-source.py, without changing geometry.

Run from the repository root:
  uv run --isolated --no-project python web/scripts/export-native-inventory.py --model /path/to/raw-native.glb \
    --source-commit 81539e53f5146c06a77541415bd79da673806d96 \
    --expected-model-sha256 60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c \
    --output /tmp/native-model-inventory.json

Requires Python and Node, not the fitter's numerical dependencies. The tracked
approval and sole CAD identity map are authoritative; caller flags cannot replace
them. `sha256` remains the original raw-model identity expected by fit-source.py.
Rows contain canonical qualified paths and unchanged column-major local-metres
-to-world-metres matrices. The native assembly root and non-native scaffolding
are excluded from the released descendant rest-matrix census. Assemblies below
the root are included; a rest-matrix row is NOT a drawable or a part definition.
Runtime-generated instances are never exported. Bounds are not required by the
consumer, so no historical bounds or derived world landmarks are emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from native_identity_source import (
    CadIdentityMap,
    glb_nodes,
    validate_path_projection,
    validate_release_pair,
)


ROOT = Path(__file__).resolve().parents[2]
NATIVE_ROOT = "ha-harmonic-analyzer"
AUTHORITY_SCRIPT = """
import { pathToFileURL } from 'node:url';
const { APPROVED_MODEL_REPRESENTATION: approved } = await import(pathToFileURL(process.argv[1]).href);
const { nativeIdentityPaths } = await import(pathToFileURL(process.argv[2]).href);
console.log(JSON.stringify({ approved, projection: await nativeIdentityPaths(process.argv[3]) }));
"""


def native_authority(model: Path) -> dict:
    """Use the same tracked approval validator and identity projector as importers."""
    try:
        result = subprocess.check_output(
            ["node", "--input-type=module", "--eval", AUTHORITY_SCRIPT,
             str(Path(__file__).with_name("approved-model.mjs")),
             str(Path(__file__).with_name("native-identity-map.mjs")),
             str(model.resolve())],
            text=True, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Native inventory authority refused the model: {error.stderr.strip()}") from error
    return json.loads(result)


def finite_vector(value, size: int, label: str) -> None:
    if (not isinstance(value, list) or len(value) != size
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError(f"{label}: expected {size} finite numbers")


def affine_matrix(value, label: str) -> None:
    finite_vector(value, 16, label)
    if [value[i] for i in (3, 7, 11, 15)] != [0, 0, 0, 1]:
        raise ValueError(f"{label}: expected an affine column-major matrix")
    a, b, c, d, e, f, g, h, i = (value[k] for k in (0, 4, 8, 1, 5, 9, 2, 6, 10))
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if not math.isfinite(determinant) or determinant == 0:
        raise ValueError(f"{label}: singular or nonfinite transform")


def validate_transform(node: dict, label: str) -> None:
    if "matrix" in node:
        if any(key in node for key in ("translation", "rotation", "scale")):
            raise ValueError(f"{label}: matrix and TRS cannot coexist")
        affine_matrix(node["matrix"], label)
        return
    for key, size in (("translation", 3), ("rotation", 4), ("scale", 3)):
        if key in node:
            finite_vector(node[key], size, f"{label}/{key}")
    if "rotation" in node and abs(sum(x * x for x in node["rotation"]) - 1) > 1e-5:
        raise ValueError(f"{label}: rotation must be a unit quaternion (not normalized by exporter)")
    if "scale" in node and any(x == 0 for x in node["scale"]):
        raise ValueError(f"{label}: singular scale")


def scene_nodes(document: dict) -> dict[str, dict]:
    """Inspect active-scene metadata only; glb_nodes remains the transform authority."""
    nodes, scenes = document["nodes"], document["scenes"]
    scene = document.get("scene", 0)
    if type(scene) is not int or not 0 <= scene < len(scenes):
        raise ValueError("Invalid active native scene")
    result, visited = {}, set()
    stack = [(index, "") for index in reversed(scenes[scene]["nodes"])]
    while stack:
        index, prefix = stack.pop()
        if type(index) is not int or not 0 <= index < len(nodes) or index in visited:
            raise ValueError("Invalid, repeated or cyclic native scene node")
        visited.add(index)
        node = nodes[index]
        name = node.get("name")
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValueError(f"Node {index}: missing or ambiguous qualified name")
        path = f"{prefix}/{name}" if prefix else name
        if path in result:
            raise ValueError(f"Duplicate qualified model path: {path}")
        validate_transform(node, path)
        result[path] = node
        stack.extend((child, path) for child in reversed(node.get("children", [])))
    if len(visited) != len(nodes):
        raise ValueError("Approved inventory requires every artifact node in the active scene")
    return result


def read_native_nodes(model: Path) -> tuple[dict, dict, dict, str]:
    parsed_digest = hashlib.sha256()
    with model.open("rb") as stream:
        header = stream.read(12)
        chunk_header = stream.read(8)
        parsed_digest.update(header)
        parsed_digest.update(chunk_header)
        magic, version, size = struct.unpack("<III", header)
        length, kind = struct.unpack("<II", chunk_header)
        if (magic != 0x46546C67 or version != 2 or size != os.fstat(stream.fileno()).st_size
                or kind != 0x4E4F534A or length % 4 or 20 + length > size):
            raise ValueError("Not a complete GLB 2 file with a JSON first chunk")
        text = stream.read(length)
        parsed_digest.update(text)
        document = json.loads(text)
        bytes_read = 20 + len(text)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            parsed_digest.update(chunk)
            bytes_read += len(chunk)
        if bytes_read != size:
            raise ValueError("GLB changed length while reading native census")
    metadata = scene_nodes(document)
    raw_nodes, digest = glb_nodes(model)
    if digest != parsed_digest.hexdigest():
        raise ValueError("GLB changed between native census and transform reads")
    if set(raw_nodes) != set(metadata):
        raise ValueError("Raw transform paths differ from active-scene metadata")
    for path, world in raw_nodes.items():
        affine_matrix(world, f"{path}/world")
    return document, metadata, raw_nodes, digest


def assemble_inventory(document: dict, metadata: dict, raw_nodes: dict, raw_sha256: str,
                       projection: dict, approved: dict, identity_map: CadIdentityMap,
                       source_commit: str, expected_model_sha256: str) -> dict:
    validate_release_pair(source_commit, expected_model_sha256)
    source = {"sha256": expected_model_sha256, "sourceCommit": source_commit}
    if approved["source"] != source:
        raise ValueError("Requested raw/source pair differs from the tracked approved native release")
    if raw_sha256 != expected_model_sha256:
        raise ValueError("Raw model SHA256 differs from the approved original native model")
    if projection.get("identity") != approved["identity"]:
        raise ValueError("Canonical projection differs from the approved map/identity epoch")
    canonical_nodes, identity = validate_path_projection(raw_nodes, raw_sha256, projection, identity_map)
    rows = projection["paths"]
    if sum(row["canonical"] == NATIVE_ROOT for row in rows) != 1:
        raise ValueError("Expected exactly one canonical native assembly root")
    inventory = [
        {"path": row["canonical"], "sourcePath": row["source"], "world": canonical_nodes[row["canonical"]]}
        for row in rows if row["canonical"] != NATIVE_ROOT
    ]
    mesh_nodes = [node for node in metadata.values() if "mesh" in node]
    drawable_count = 0
    for node in mesh_nodes:
        index = node["mesh"]
        meshes = document.get("meshes", [])
        if type(index) is not int or not 0 <= index < len(meshes):
            raise ValueError("Native drawable references a missing mesh")
        primitives = meshes[index].get("primitives")
        if not isinstance(primitives, list) or not primitives:
            raise ValueError("Native mesh has no drawable primitives")
        drawable_count += len(primitives)
    if drawable_count != approved["equivalence"]["drawableCount"]:
        raise ValueError("Artifact drawable census differs from the tracked approval")
    native_mesh_count = sum("mesh" in metadata[item["sourcePath"]] for item in inventory)
    return {
        "sha256": raw_sha256,
        "source": source,
        "identity": identity,
        "matrixConvention": "column-major part-local-metres to native-world-metres",
        "census": {
            "artifactNodeCount": len(document["nodes"]),
            "nativeRootCount": 1,
            "releasedDescendantRestMatrixCount": len(inventory),
            "releasedMeshNodeCount": native_mesh_count,
            "releasedNonMeshTransformCount": len(inventory) - native_mesh_count,
            "artifactDrawableCount": drawable_count,
            "nonNativeNodeCount": len(raw_nodes) - len(rows),
            "instanceScope": "released-native-descendants",
            "runtimeCensus": "not configured",
        },
        "inventory": inventory,
    }


def export_inventory(model: Path, source_commit: str, expected_model_sha256: str) -> dict:
    validate_release_pair(source_commit, expected_model_sha256)
    authority = native_authority(model)
    document, metadata, raw_nodes, digest = read_native_nodes(model)
    return assemble_inventory(
        document, metadata, raw_nodes, digest, authority["projection"], authority["approved"],
        CadIdentityMap(ROOT), source_commit, expected_model_sha256,
    )


def publish_inventory(output: Path, encoded: str) -> None:
    """Replace the directory entry, never write through an existing output alias."""
    candidate = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=f".{output.name}.", suffix=".tmp", delete=False,
        ) as stream:
            candidate = Path(stream.name)
            stream.write(encoded)
        os.replace(candidate, output)
    finally:
        if candidate is not None:
            candidate.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        model = args.model.resolve()
        cad = ROOT / "cad"
        if (output == model or (output.exists() and output.samefile(model))
                or output.is_relative_to(cad)
                or Path(os.path.abspath(args.output)).is_relative_to(cad)):
            raise ValueError("The native model and CAD tree are read-only")
        inventory = export_inventory(args.model, args.source_commit, args.expected_model_sha256)
        encoded = json.dumps(inventory, indent=2, allow_nan=False) + "\n"
        publish_inventory(args.output, encoded)
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        parser.error(str(error))
    print(json.dumps({"output": str(args.output), "sha256": inventory["sha256"],
                      "identity": inventory["identity"], "census": inventory["census"]}, indent=2))


if __name__ == "__main__":
    main()
