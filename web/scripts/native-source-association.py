#!/usr/bin/env python3
"""Pure original-GLB association; no renderer, CAD execution, fitting or qualification.

An unchanged typed primitive at the same exact qualified path can retain its
already identified local feature. Old world coordinates are first localized in
THE OLD frame, then transported by the new frame. Changed, absent or ambiguous
features have no current native point. This proof never transfers camera/GPU fits.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import struct
from functools import lru_cache
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
HISTORICAL_SOURCE = {
    "sha256": "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d",
    "sourceCommit": "1268c23d4a8fc741147c5e09d8d1e45247a71945",
}
APPROVED_SOURCE = {
    "sha256": "60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c",
    "sourceCommit": "81539e53f5146c06a77541415bd79da673806d96",
}
IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
COMPONENTS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
              5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
DIMENSIONS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def json_digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def finite_vector(value, size):
    return (isinstance(value, list) and len(value) == size
            and all(type(x) in (int, float) and math.isfinite(x) for x in value))


def multiply(a, b):
    return [sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
            for col in range(4) for row in range(4)]


def node_matrix(node):
    if "matrix" in node:
        if any(key in node for key in ("translation", "rotation", "scale")):
            raise ValueError("Native node declares both matrix and TRS")
        matrix = node["matrix"]
    else:
        rotation = node.get("rotation", [0., 0., 0., 1.])
        scale = node.get("scale", [1., 1., 1.])
        translation = node.get("translation", [0., 0., 0.])
        if not finite_vector(rotation, 4) or not finite_vector(scale, 3) or not finite_vector(translation, 3):
            raise ValueError("Native node TRS must be finite")
        x, y, z, w = rotation
        sx, sy, sz = scale
        tx, ty, tz = translation
        matrix = [(1-2*(y*y+z*z))*sx, 2*(x*y+z*w)*sx, 2*(x*z-y*w)*sx, 0.,
                  2*(x*y-z*w)*sy, (1-2*(x*x+z*z))*sy, 2*(y*z+x*w)*sy, 0.,
                  2*(x*z+y*w)*sz, 2*(y*z-x*w)*sz, (1-2*(x*x+y*y))*sz, 0.,
                  tx, ty, tz, 1.]
    if not finite_vector(matrix, 16) or matrix[3::4] != [0, 0, 0, 1]:
        raise ValueError("Native world frame must be a finite affine matrix")
    return matrix


def transform(matrix, point):
    return [sum(matrix[k*4+row]*point[k] for k in range(3)) + matrix[12+row]
            for row in range(3)]


def localize_old_world(matrix, point):
    """Solve old affine frame only; never invert the new matrix to keep old world."""
    rows = [[matrix[col*4+row] for col in range(3)] + [point[row]-matrix[12+row]]
            for row in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(rows[row][col]))
        if rows[pivot][col] == 0:
            raise ValueError("Old native frame is singular")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [value/scale for value in rows[col]]
        for row in range(3):
            if row != col:
                scale = rows[row][col]
                rows[row] = [a-scale*b for a, b in zip(rows[row], rows[col])]
    result = [rows[row][3] for row in range(3)]
    if not finite_vector(result, 3):
        raise ValueError("Old native local feature is not finite")
    return result


def current_model_identity():
    """Descriptor source is the caller authority; the closed release tuple is integrity."""
    descriptor = json.loads((WEB / "content/model-representation.json").read_text())
    representation = descriptor.get("representation", {})
    pipeline = descriptor.get("pipeline", {})
    equivalence = descriptor.get("equivalence", {})
    valid_hash = lambda value: isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    if (set(descriptor) != {"schemaVersion", "kind", "source", "representation", "pipeline", "equivalence"}
            or descriptor["schemaVersion"] != 1
            or descriptor["kind"] != "lossless-web-model-representation"
            or descriptor["source"] != APPROVED_SOURCE
            or set(representation) != {"path", "sha256", "byteLength", "codec"}
            or representation["path"] != "models/harmonic-analyzer.glb"
            or not valid_hash(representation["sha256"])
            or type(representation["byteLength"]) is not int or representation["byteLength"] <= 0
            or representation["codec"] != "EXT_meshopt_compression"
            or set(pipeline) != {"version", "steps", "codecVersion"} or pipeline["version"] != 1
            or pipeline["steps"] != ["exact-dedup", "meshopt"]
            or not isinstance(pipeline["codecVersion"], str) or re.fullmatch(r"meshoptimizer@[0-9]+[.][0-9]+[.][0-9]+", pipeline["codecVersion"]) is None
            or set(equivalence) != {"method", "semanticSha256", "drawableCount"}
            or equivalence["method"] != "decoded-per-drawable-exact-v1"
            or not valid_hash(equivalence["semanticSha256"])
            or type(equivalence["drawableCount"]) is not int or equivalence["drawableCount"] <= 0):
        raise ValueError("Current tracked descriptor is not the approved native source representation")
    return {**descriptor["source"], "units": "metres", "axes": "X-width/Y-height/Z-depth"}


class RawNativeModel:
    """Decode actual typed storage and qualified instance frames from one raw GLB."""
    def __init__(self, path, expected_sha256):
        self.path = Path(path)
        data = self.path.read_bytes()
        self.sha256 = hashlib.sha256(data).hexdigest()
        if self.sha256 != expected_sha256:
            raise ValueError(f"Original native cache SHA256 mismatch: {self.path}")
        if len(data) < 28:
            raise ValueError("Truncated original native GLB")
        magic, version, total = struct.unpack_from("<III", data)
        length, kind = struct.unpack_from("<II", data, 12)
        if (magic, version, total, kind) != (0x46546C67, 2, len(data), 0x4E4F534A):
            raise ValueError("Expected complete original GLB2 JSON chunk")
        end = 20 + length
        self.document = json.loads(data[20:end])
        binary_length, binary_kind = struct.unpack_from("<II", data, end)
        if binary_kind != 0x004E4942 or end + 8 + binary_length != total:
            raise ValueError("Expected exactly one embedded original GLB binary chunk")
        self.binary = memoryview(data)[end+8:]
        buffers = self.document.get("buffers", [])
        if len(buffers) != 1 or "uri" in buffers[0] or buffers[0]["byteLength"] > binary_length:
            raise ValueError("External or missing native GLB buffer")
        self.parts = {}
        self._accessors = {}
        self._primitives = {}
        self._bounds = {}
        active = set()

        def visit(index, prefix, parent):
            if index in active:
                raise ValueError("Cyclic original native hierarchy")
            active.add(index)
            node = self.document["nodes"][index]
            name = node.get("name")
            if not isinstance(name, str) or not name or "/" in name:
                raise ValueError("Original native part needs an unambiguous authored name")
            path = f"{prefix}/{name}" if prefix else name
            if path in self.parts:
                raise ValueError(f"Duplicate original native qualified path: {path}")
            world = multiply(parent, node_matrix(node))
            self.parts[path] = {"nodeIndex": index, "node": node, "worldMatrix": world}
            for child in node.get("children", []):
                visit(child, path, world)
            active.remove(index)

        scene = self.document["scenes"][self.document.get("scene", 0)]
        for root in scene["nodes"]:
            visit(root, "", IDENTITY)

    def view_bytes(self, index):
        view = self.document["bufferViews"][index]
        if view.get("buffer", 0) != 0 or view.get("extensions"):
            raise ValueError("Native original bufferView must be uncompressed embedded storage")
        start, length = view.get("byteOffset", 0), view["byteLength"]
        if type(start) is not int or type(length) is not int or start < 0 or length < 0 or start+length > len(self.binary):
            raise ValueError("Native bufferView exceeds original binary")
        return self.binary[start:start+length]

    def accessor(self, index):
        if index in self._accessors:
            return self._accessors[index]
        entry = self.document["accessors"][index]
        if entry.get("sparse") or entry.get("extensions") or entry["type"] not in DIMENSIONS:
            raise ValueError("Unsupported native sparse/compressed/matrix accessor")
        code, size = COMPONENTS[entry["componentType"]]
        width = DIMENSIONS[entry["type"]] * size
        count = entry["count"]
        view = self.document["bufferViews"][entry["bufferView"]]
        storage = self.view_bytes(entry["bufferView"])
        stride, offset = view.get("byteStride", width), entry.get("byteOffset", 0)
        if (type(count) is not int or count < 1 or type(stride) is not int or stride < width
                or type(offset) is not int or offset < 0 or offset + (count-1)*stride + width > len(storage)):
            raise ValueError("Native accessor typed span exceeds original bufferView")
        dense = bytes(storage[offset:offset+count*width]) if stride == width else b"".join(
            storage[offset+i*stride:offset+i*stride+width] for i in range(count))
        signature = {"componentType": entry["componentType"], "type": entry["type"], "count": count,
                     "normalized": entry.get("normalized", False), "typedBytesSha256": hashlib.sha256(dense).hexdigest()}
        if code == "f" and any(not math.isfinite(value[0]) for value in struct.iter_unpack("<f", dense)):
            raise ValueError("Nonfinite original native float attribute")
        self._accessors[index] = signature, dense
        return self._accessors[index]

    def material(self, index):
        if index is None:
            return None
        material = copy.deepcopy(self.document["materials"][index])

        def resolve(value):
            if isinstance(value, dict):
                for key, child in list(value.items()):
                    if key.endswith("Texture") and isinstance(child, dict) and "index" in child:
                        texture = copy.deepcopy(self.document["textures"][child["index"]])
                        if "extensions" in texture:
                            raise ValueError("Unsupported native texture extension")
                        image = self.document["images"][texture.pop("source")]
                        if "uri" in image:
                            raise ValueError("External native image is not original embedded geometry authority")
                        texture["image"] = {"mimeType": image["mimeType"],
                            "bytesSha256": hashlib.sha256(self.view_bytes(image["bufferView"])).hexdigest()}
                        if "sampler" in texture:
                            texture["sampler"] = self.document["samplers"][texture["sampler"]]
                        child["index"] = texture
                    else:
                        resolve(child)
            elif isinstance(value, list):
                for child in value:
                    resolve(child)
        resolve(material)
        return material

    def primitives(self, path):
        if path in self._primitives:
            return self._primitives[path]
        node = self.parts[path]["node"]
        if "mesh" not in node or any(key in node for key in ("skin", "weights", "extensions")):
            raise ValueError("Native feature must belong to one original rigid mesh instance")
        mesh = self.document["meshes"][node["mesh"]]
        if any(key in mesh for key in ("weights", "extensions")):
            raise ValueError("Unsupported original native mesh modifiers")
        result = []
        for primitive in mesh["primitives"]:
            if set(primitive) - {"mode", "attributes", "indices", "material"}:
                raise ValueError("Unsupported original native primitive modifiers")
            attrs = primitive["attributes"]
            if "POSITION" not in attrs or "NORMAL" not in attrs or "indices" not in primitive or primitive.get("mode", 4) != 4:
                raise ValueError("Native association needs indexed triangle POSITION and NORMAL")
            attributes = {key: self.accessor(value)[0] for key, value in sorted(attrs.items())}
            positions, normals = attributes["POSITION"], attributes["NORMAL"]
            if any((item["componentType"], item["type"], item["normalized"]) != (5126, "VEC3", False)
                   for item in (positions, normals)) or any(item["count"] != positions["count"] for item in attributes.values()):
                raise ValueError("Native triangle attributes have incompatible typed vertex spans")
            indices, index_bytes = self.accessor(primitive["indices"])
            if (indices["type"] != "SCALAR" or indices["normalized"] or indices["count"] % 3
                    or indices["componentType"] not in (5121, 5123, 5125)):
                raise ValueError("Native triangle indices have an invalid typed span")
            code = COMPONENTS[indices["componentType"]][0]
            if any(index[0] >= positions["count"] for index in struct.iter_unpack("<" + code, index_bytes)):
                raise ValueError("Native triangle index exceeds the actual vertex span")
            result.append({"mode": primitive.get("mode", 4), "attributes": attributes,
                           "indices": indices, "material": self.material(primitive.get("material"))})
        if not result:
            raise ValueError("Native feature has no actual primitive")
        self._primitives[path] = result
        return result

    def bounds(self, path):
        if path in self._bounds:
            return self._bounds[path]
        node = self.parts[path]["node"]
        local_min, local_max = [math.inf]*3, [-math.inf]*3
        world_min, world_max = [math.inf]*3, [-math.inf]*3
        for primitive in self.document["meshes"][node["mesh"]]["primitives"]:
            signature, dense = self.accessor(primitive["attributes"]["POSITION"])
            if (signature["componentType"], signature["type"], signature["normalized"]) != (5126, "VEC3", False):
                raise ValueError("Framing requires actual float32 native POSITION")
            for point in struct.iter_unpack("<fff", dense):
                world_point = transform(self.parts[path]["worldMatrix"], point)
                for axis in range(3):
                    local_min[axis] = min(local_min[axis], point[axis])
                    local_max[axis] = max(local_max[axis], point[axis])
                    world_min[axis] = min(world_min[axis], world_point[axis])
                    world_max[axis] = max(world_max[axis], world_point[axis])
        result = {"localBoundsMetres": {"min": local_min, "max": local_max},
                  "worldBoundsMetres": {"min": world_min, "max": world_max}}
        self._bounds[path] = result
        return result


class NativeAssociation:
    def __init__(self, old, new):
        self.old, self.new = old, new

    def associate_native_part(self, path):
        """Narrow exact rigid-body proof for source contour roles, without a made-up point."""
        proof = {"method": "exact-original-native-primitive-role-v1",
                 "historicalSource": {**HISTORICAL_SOURCE, "sha256": self.old.sha256},
                 "currentSource": {**APPROVED_SOURCE, "sha256": self.new.sha256},
                 "qualifiedPartPath": path}
        reason = None
        if not isinstance(path, str) or "@" in path or path not in self.old.parts or path not in self.new.parts:
            reason = "Exact original authored native body is absent; no replacement or alias inferred"
        else:
            old_part, new_part = self.old.parts[path], self.new.parts[path]
            proof.update({"historicalWorldMatrix": old_part["worldMatrix"], "currentWorldMatrix": new_part["worldMatrix"]})
            try:
                old_primitives, new_primitives = self.old.primitives(path), self.new.primitives(path)
                proof.update({"historicalPrimitiveSha256": json_digest(old_primitives),
                              "currentPrimitiveSha256": json_digest(new_primitives), "primitives": new_primitives})
                if old_primitives != new_primitives:
                    reason = "Original native typed primitives or material role changed; fresh contour/body mapping required"
            except (KeyError, IndexError, TypeError, ValueError) as error:
                reason = str(error)
        return {"status": "unavailable" if reason else "mapped", "reason": reason, "proof": proof}

    def associate_native_anchor(self, anchor):
        path = anchor.get("partPath")
        proof = {"method": "exact-original-native-local-feature-v1",
                 "historicalSource": {**HISTORICAL_SOURCE, "sha256": self.old.sha256},
                 "currentSource": {**APPROVED_SOURCE, "sha256": self.new.sha256},
                 "historicalAnchorSha256": json_digest(anchor), "qualifiedPartPath": path,
                 "historicalCorrespondenceEvidence": copy.deepcopy(anchor.get("correspondenceEvidence")),
                 "qualification": "Native local feature association only; source-first-surface, fitted camera, GPU and stages unmeasured."}

        def unavailable(reason):
            item = {key: copy.deepcopy(anchor[key]) for key in ("id", "kind", "description") if key in anchor}
            item["nativeAssociation"] = {"status": "unavailable", "reason": reason, "proof": copy.deepcopy(proof)}
            return {"status": "unavailable", "anchor": item, "proof": proof, "reason": reason}

        if (not isinstance(path, str) or not path.startswith("harmonic-analyzer/") or "@" in path
                or not isinstance(anchor.get("correspondenceEvidence"), str) or not anchor["correspondenceEvidence"].strip()):
            return unavailable("Original feature has no unambiguous authored native path and source correspondence evidence")
        if path not in self.old.parts or path not in self.new.parts:
            return unavailable("Exact original qualified native body is absent; no alias or replacement feature is inferred")
        old_part, new_part = self.old.parts[path], self.new.parts[path]
        proof.update({"historicalNodeIndex": old_part["nodeIndex"], "currentNodeIndex": new_part["nodeIndex"],
                      "historicalWorldMatrix": old_part["worldMatrix"], "currentWorldMatrix": new_part["worldMatrix"],
                      "worldFrameUnchanged": old_part["worldMatrix"] == new_part["worldMatrix"]})
        try:
            old_primitives, new_primitives = self.old.primitives(path), self.new.primitives(path)
            proof.update({"historicalPrimitiveSha256": json_digest(old_primitives),
                          "currentPrimitiveSha256": json_digest(new_primitives), "primitives": new_primitives})
            if old_primitives != new_primitives:
                return unavailable("Original typed primitive attributes, indices or material role changed; feature requires fresh primary mapping")
            local, world = anchor.get("partLocalMetres"), anchor.get("worldMetres")
            if finite_vector(local, 3) == finite_vector(world, 3):
                return unavailable("Original feature needs exactly one finite native local or old-world coordinate")
            if world is not None:
                local = localize_old_world(old_part["worldMatrix"], world)
                proof["historicalWorldMetres"] = copy.deepcopy(world)
                proof["coordinateBasis"] = "old-world localized by actual old frame, transported by actual new frame"
            else:
                proof["coordinateBasis"] = "unchanged identified old native local feature"
            proof.update({"partLocalMetres": copy.deepcopy(local),
                          "currentRestWorldMetres": transform(new_part["worldMatrix"], local)})
            item = {key: copy.deepcopy(anchor[key]) for key in ("id", "kind", "description") if key in anchor}
            item.update({"partPath": path, "partLocalMetres": copy.deepcopy(local),
                         "correspondenceEvidence": "Original source feature identity retained by the historical anchor digest and correspondence evidence in nativeAssociation.proof. Exact original typed primitives and current authored frame independently associated; source-first-surface, fitted-camera and GPU qualification remain unmeasured.",
                         "nativeAssociation": {"status": "mapped", "reason": None, "proof": copy.deepcopy(proof)}})
            return {"status": "mapped", "anchor": item, "proof": proof, "reason": None}
        except (KeyError, IndexError, TypeError, ValueError) as error:
            return unavailable(str(error))


@lru_cache(maxsize=1)
def native_association():
    current_model_identity()
    cache = WEB / ".vite/model-source"
    old = RawNativeModel(cache / f'{HISTORICAL_SOURCE["sha256"]}.glb', HISTORICAL_SOURCE["sha256"])
    new = RawNativeModel(cache / f'{APPROVED_SOURCE["sha256"]}.glb', APPROVED_SOURCE["sha256"])
    return NativeAssociation(old, new)


def associate_native_anchor(anchor):
    return native_association().associate_native_anchor(anchor)


def associate_native_part(path):
    return native_association().associate_native_part(path)


def current_native_paths():
    return frozenset(native_association().new.parts)


def current_native_parts():
    model = native_association().new
    return {path: {"worldMatrix": copy.deepcopy(part["worldMatrix"]),
                   "primitiveCount": len(model.document["meshes"][part["node"]["mesh"]]["primitives"]),
                   **copy.deepcopy(model.bounds(path))}
            for path, part in model.parts.items() if "mesh" in part["node"]}
