#!/usr/bin/env python3
"""Intro native-feature support and finite-nib eligibility, CPU only.

The exact stored local POSITION equivalence class supplies incident facets, not
additional calibration points. A full435 first-surface result remains conditional
on the sealed chosen input/export epoch and does not identify the source nib.
Operation requires a fresh native export and refuses any native code differing
from --code-root. Historical snapshots are not a current eligibility authority.
Every primitive, including hidden ones, must cover exact sealed little-endian
float64 XYZ / uint32 triangle bytes with finite positions and local index bounds.
Camera rotations must satisfy R.T @ R = I and determinant +1 within 1e-6 absolute
rounding tolerance; no normalization or clipping-axis repair is performed.
These admissibility checks do not relax the 1e-7 m nib epsilon, 5 mm / 100 m
near/far clipping, or independent 96 px / 0.5 s source obligations.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import mmap
import re
import struct
from pathlib import Path

import numpy as np

WEB = Path(__file__).resolve().parents[1]
PROFILE = WEB / "content" / "NAsM30MAHLg.calibration-eligibility.json"
common_spec = importlib.util.spec_from_file_location(
    "native_feature_source_common", Path(__file__).with_name("compact-source-common.py"),
)
common = importlib.util.module_from_spec(common_spec)
common_spec.loader.exec_module(common)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sha256_string(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def finite_ray_array(value, shape, label):
    if not isinstance(value, (list, tuple, np.ndarray)):
        raise ValueError(f"{label} must be finite numeric data of shape {shape}")
    array = np.asarray(value)
    if array.shape != shape or array.dtype.kind not in "iuf" or not np.all(np.isfinite(array)):
        raise ValueError(f"{label} must be finite numeric data of shape {shape}")
    if isinstance(value, (list, tuple)):
        numbers = value if len(shape) == 1 else (number for row in value for number in row)
        if any(isinstance(number, (bool, np.bool_)) for number in numbers):
            raise ValueError(f"{label} must contain numbers, not booleans")
    return array


def proper_camera_rotation(value):
    """Admit float32-rounded camera rotations without changing clipping gates."""
    rotation = finite_ray_array(value, (3, 3), "Ray rotation").astype(np.float64, copy=False)
    tolerance = 1e-6
    # Bound the entries before products so malformed finite values cannot
    # overflow, then require SO(3), not a scale/shear/reflection camera.
    if (np.max(np.abs(rotation)) > 1 + tolerance
            or np.max(np.abs(rotation.T @ rotation - np.eye(3))) > tolerance
            or abs(np.linalg.det(rotation) - 1) > tolerance):
        raise ValueError("Ray rotation must be a proper orthonormal camera rotation")
    return rotation


def request_has_nonfinite(value):
    if isinstance(value, dict):
        return any(request_has_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(request_has_nonfinite(item) for item in value)
    return type(value) is float and not math.isfinite(value)


def calibration_support(frame, points, policy):
    """Refuse repeated native support before fitting; never alter source rows."""
    groups = {role: [p for p in frame["landmarks"] if p["role"] == role]
              for role in ("fit", "check")}
    coordinates = {role: np.asarray([points[p["anchorId"]] for p in rows], dtype=float).reshape(-1, 3)
                   for role, rows in groups.items()}
    separation = policy["supportSeparationMetres"]
    collisions = []
    all_rows = [(role, row, xyz) for role in groups
                for row, xyz in zip(groups[role], coordinates[role])]
    for i, (role, row, xyz) in enumerate(all_rows):
        if not np.all(np.isfinite(xyz)):
            raise ValueError(f"{row['anchorId']}: native support is not finite")
        for other_role, other, other_xyz in all_rows[:i]:
            if np.linalg.norm(xyz - other_xyz) <= separation:
                collisions.append({"anchorIds": [other["anchorId"], row["anchorId"]],
                                   "roles": [other_role, role],
                                   "reason": "Coincident actual native 3D support is one physical feature, not independent declarations."})
    xyz = coordinates["fit"]
    rank = int(np.linalg.matrix_rank(xyz - xyz.mean(axis=0), tol=policy["rankToleranceMetres"])) if len(xyz) else 0
    eligible = (not collisions and len(xyz) >= policy["minimumDistinctFitPoints"]
                and len(coordinates["check"]) >= policy["minimumIndependentCheckPoints"]
                and rank >= policy["minimumFitAffineRank"])
    return {"eligible": bool(eligible), "declaredFitPoints": len(xyz),
            "declaredCheckPoints": len(coordinates["check"]), "fitAffineRank": rank,
            "coincidentNativeSupport": collisions,
            "reason": None if eligible else "Calibration needs distinct actual native FIT support and disjoint independent CHECK support with sufficient affine rank.",
            "qualification": "CPU geometric eligibility only; source association, positive depth, physical complete input and native raster proof remain required."}


def stored_primitive(model_path, part_path, primitive_index, expected_hash):
    """Read original local attributes directly; inverse-posed floats are not identity."""
    if digest(model_path) != expected_hash:
        raise ValueError("Original raw native model differs from the sealed geometry authority")
    with Path(model_path).open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        magic, version, total = struct.unpack_from("<III", data)
        length, kind = struct.unpack_from("<II", data, 12)
        if magic != 0x46546C67 or version != 2 or total != len(data) or kind != 0x4E4F534A:
            raise ValueError("Expected original GLB2 geometry")
        document = json.loads(data[20:20 + length])
        binary_length, binary_kind = struct.unpack_from("<II", data, 20 + length)
        binary_start = 28 + length
        if binary_kind != 0x004E4942 or binary_start + binary_length != total:
            raise ValueError("Expected one embedded original GLB buffer")
        nodes = document["nodes"]
        matches = []

        def visit(index, parent):
            node = nodes[index]
            path = f"{parent}/{node['name']}" if parent else node["name"]
            if path == part_path:
                matches.append(node)
            for child in node.get("children", []):
                visit(child, path)

        for index in document["scenes"][document.get("scene", 0)]["nodes"]:
            visit(index, "")
        if len(matches) != 1:
            raise ValueError("Native feature must resolve to exactly one original named part")
        primitive = document["meshes"][matches[0]["mesh"]]["primitives"][primitive_index]
        if primitive.get("mode", 4) != 4:
            raise ValueError("Native finite feature needs an original triangle primitive")

        def accessor(index):
            entry = document["accessors"][index]
            view = document["bufferViews"][entry["bufferView"]]
            dimensions = {"SCALAR": 1, "VEC3": 3}[entry["type"]]
            dtype = np.dtype({5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "u1"}[entry["componentType"]])
            if view.get("buffer", 0) != 0 or "sparse" in entry or entry.get("normalized"):
                raise ValueError("Original feature requires unmodified stored local attributes")
            return np.ndarray((entry["count"], dimensions), dtype=dtype, buffer=data,
                              offset=binary_start + view.get("byteOffset", 0) + entry.get("byteOffset", 0),
                              strides=(view.get("byteStride", dimensions * dtype.itemsize), dtype.itemsize)).copy()

        positions = accessor(primitive["attributes"]["POSITION"])
        indices = accessor(primitive["indices"]).reshape(-1, 3)
    return positions, indices


class FrozenNativeFirstSurface:
    """Complete native CPU ray gate with exact same-primitive apex support."""
    def __init__(self, export_path, model_path, profile, code_root=WEB.parent):
        self.export_path = Path(export_path)
        self.export_sha256 = digest(self.export_path)
        self.export = json.loads(self.export_path.read_text())
        if not isinstance(self.export, dict):
            raise ValueError("Complete native export must be a sealed object, not null")
        self.profile = profile
        self.nib = profile["finiteNib"]
        source_identity = self.export.get("modelSourceSha256", self.export.get("modelSha256"))
        if (not sha256_string(self.export.get("modelSha256"))
                or source_identity != profile["modelSha256"]):
            raise ValueError("Posed export does not identify the original native source geometry")
        fields = self.export.get("unobservedInputFields")
        if (not isinstance(fields, list) or len(fields) != len(common.INPUT_FIELDS)
                or not all(isinstance(field, str) for field in fields)
                or set(fields) != set(common.INPUT_FIELDS)
                or self.export.get("nativeDrawableDenominator") != self.nib["requiredNativeDrawableCount"]
                or self.export.get("springDrawableCount") != self.nib["requiredSpringDrawableCount"]
                or self.export.get("inputMechanismAndAll435ArraysFrozenAsOneState") is not True
                or self.export.get("partOverrides") != []):
            raise ValueError("Finite nib requires one complete chosen51/all435/21-spring native state, without detached overrides")
        hashes = self.export.get("codeHashes")
        if (not isinstance(hashes, dict) or not hashes
                or any(not isinstance(path, str) or not path or not sha256_string(sha)
                       for path, sha in hashes.items())):
            raise ValueError("Native codeHashes must be a nonempty path-to-SHA256 object")
        snapshots = self.export.get("actuallyExecutedImmutableNativeSourceSnapshots")
        if (not isinstance(snapshots, list) or not snapshots
                or any(not isinstance(row, dict)
                       or not isinstance(row.get("relativePath"), str) or not row["relativePath"]
                       or not isinstance(row.get("snapshotPath"), str) or not row["snapshotPath"]
                       or not sha256_string(row.get("sha256")) for row in snapshots)):
            raise ValueError("Executed native snapshots must contain path and SHA256 records")
        chosen_input = self.export.get("input")
        if (not isinstance(chosen_input, dict)
                or not isinstance(chosen_input.get("setup"), dict)
                or any(not isinstance(chosen_input.get(name), list) for name in ("amplitudes", "phases"))):
            raise ValueError("Chosen native input must contain the complete scalar, channel and setup state")
        compact_input = common.compact_input(chosen_input)
        numbers = [compact_input["crankTurns"], compact_input["magnification"]]
        numbers += compact_input["amplitudes"] + compact_input["phases"]
        numbers += [value for value in compact_input["setup"].values() if value is not None]
        if chosen_input != compact_input or any(type(value) not in (int, float) for value in numbers):
            raise ValueError("Chosen native input must be exactly the complete51 numerically typed state")
        geometry = self.export.get("geometry")
        if (not isinstance(geometry, dict)
                or any(not isinstance(geometry.get(name), dict)
                       or not isinstance(geometry[name].get("path"), str) or not geometry[name]["path"]
                       or not sha256_string(geometry[name].get("sha256"))
                       for name in ("positions", "indices"))):
            raise ValueError("Complete posed all435 arrays require sealed position/index path and SHA256 records")
        census = self.export.get("census")
        if not isinstance(census, list) or len(census) != self.nib["requiredNativeDrawableCount"]:
            raise ValueError("Incomplete actual native census")
        for row in census:
            if (not isinstance(row, dict)
                    or not isinstance(row.get("path"), str) or not row["path"]
                    or any(type(row.get(key)) is not int or row[key] < 0 for key in
                           ("positionByteOffset", "indexByteOffset", "vertexCount", "indexCount"))
                    or not row["vertexCount"] or not row["indexCount"] or row["indexCount"] % 3
                    or row["positionByteOffset"] % 8 or row["indexByteOffset"] % 4
                    or not isinstance(row.get("matrixWorld"), list) or len(row["matrixWorld"]) != 16
                    or any(type(value) not in (int, float) or not math.isfinite(value)
                           for value in row["matrixWorld"])
                    or type(row.get("visibleByNativeGraph")) is not bool):
                raise ValueError("Native census rows require complete finite primitive pose/count/visibility metadata")
        closure_hashes = {row["relativePath"]: row["sha256"] for row in snapshots}
        if len(closure_hashes) != len(snapshots) or any(
                closure_hashes.get(path) != sha for path, sha in hashes.items()):
            raise ValueError("Executed native closure does not seal the declared native code")
        self.code_paths = [(Path(code_root) / path, sha) for path, sha in closure_hashes.items()]
        for row in snapshots:
            if digest(row["snapshotPath"]) != row["sha256"]:
                raise ValueError("Actually executed native snapshot differs from its sealed closure")
        self.assert_code()
        local, triangles = stored_primitive(model_path, self.nib["partPath"], self.nib["primitiveIndex"], profile["modelSha256"])
        vertex = self.nib["nativeVertexIndex"]
        if not np.array_equal(local[vertex], self.nib["storedPartLocalMetres"]):
            raise ValueError("Declared nib is not the exact actual stored native local apex")
        self.equivalent_vertices = np.flatnonzero(np.all(local == local[vertex], axis=1))
        self.incident_nib_triangles = np.flatnonzero(np.isin(triangles, self.equivalent_vertices).any(axis=1))
        self.parts = {}
        arrays = {}
        for name, dtype, declared_dtype in (
                ("positions", "<f8", "little-endian IEEE754 float64"),
                ("indices", "<u4", "little-endian uint32")):
            entry = geometry[name]
            path = self.export_path.parent / entry["path"]
            size = path.stat().st_size
            if (entry.get("dtype") != declared_dtype
                    or type(entry.get("bytes")) is not int or entry["bytes"] != size
                    or size <= 0 or size % np.dtype(dtype).itemsize):
                raise ValueError("Posed native arrays require exact dtype and complete aligned byte lengths")
            if digest(path) != entry["sha256"]:
                raise ValueError("Posed native array differs from its sealed export")
            arrays[name] = np.memmap(path, dtype=dtype, mode="r")
        position_end, index_end = 0, 0
        for row in census:
            path = row["path"]
            if path in self.parts:
                raise ValueError("Duplicate actual native primitive path")
            if (row["positionByteOffset"] != position_end or row["indexByteOffset"] != index_end
                    or row["vertexCount"] > arrays["positions"].size // 3
                    or row["indexCount"] > arrays["indices"].size):
                raise ValueError("Native primitive slices must be bounded and contiguous over the complete arrays")
            position_bytes, index_bytes = row["vertexCount"] * 24, row["indexCount"] * 4
            position_end += position_bytes
            index_end += index_bytes
            if (position_end > arrays["positions"].nbytes or index_end > arrays["indices"].nbytes
                    or row.get("positionBytes", position_bytes) != position_bytes
                    or row.get("indexBytes", index_bytes) != index_bytes):
                raise ValueError("Native primitive counts must exactly cover their declared position/index slices")
            p_offset, f_offset = row["positionByteOffset"] // 8, row["indexByteOffset"] // 4
            positions = arrays["positions"][p_offset:p_offset + row["vertexCount"] * 3].reshape(row["vertexCount"], 3)
            faces = arrays["indices"][f_offset:f_offset + row["indexCount"]].reshape(row["indexCount"] // 3, 3)
            if not np.all(np.isfinite(positions)) or faces.max() >= row["vertexCount"]:
                raise ValueError("Every native primitive requires finite coordinates and primitive-local triangle indices")
            self.parts[path] = {"P": positions, "F": faces, "M": np.asarray(row["matrixWorld"]).reshape(4, 4, order="F"),
                                "visible": row["visibleByNativeGraph"]}
            self.parts[path]["bounds"] = (positions.min(axis=0), positions.max(axis=0))
        if position_end != arrays["positions"].nbytes or index_end != arrays["indices"].nbytes:
            raise ValueError("Native census slices must cover every byte of the sealed posed arrays")
        if len(self.parts) != self.nib["requiredNativeDrawableCount"]:
            raise ValueError("Incomplete actual native census")
        marker = self.parts[self.nib["partPath"]]
        if marker["P"].shape != local.shape or not np.array_equal(marker["F"], triangles):
            raise ValueError("Native marker support indices differ from the exact original primitive")
        expected = (marker["M"] @ np.r_[local[vertex], 1])[:3]
        if np.max(np.linalg.norm(marker["P"][self.equivalent_vertices] - expected, axis=1)) > self.nib["eligibilityEpsilonMetres"]:
            raise ValueError("Sealed apex copies are not the same actual posed native feature")
        self.assert_code()

    def assert_code(self):
        for path, sha in self.code_paths:
            if digest(path) != sha:
                raise ValueError(f"Native code differs from sealed export: {path}")

    def first_surface(self, origin, direction, near_t, far_t):
        origin = finite_ray_array(origin, (3,), "Ray origin")
        direction = finite_ray_array(direction, (3,), "Ray direction")
        best = None
        nonzero = abs(direction) > 1e-15
        direction_inverse = np.divide(1., direction, out=np.zeros(3), where=nonzero)
        for path, part in self.parts.items():
            if not part["visible"]:
                continue
            positions = part["P"]
            lo, hi = part["bounds"]
            if np.any(~nonzero & ((origin < lo) | (origin > hi))):
                continue
            aa, bb = (lo - origin) * direction_inverse, (hi - origin) * direction_inverse
            entry = max(np.where(nonzero, np.minimum(aa, bb), -np.inf).max(), near_t)
            exit_t = min(np.where(nonzero, np.maximum(aa, bb), np.inf).min(), far_t)
            if entry > exit_t or best is not None and entry > best["segmentParameter"]:
                continue
            if "triangleData" not in part:
                triangles = positions[part["F"]]
                e1, e2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
                part["triangleData"] = (triangles, e1, e2)
            else:
                triangles, e1, e2 = part["triangleData"]
            h = np.cross(direction, e2)
            den = np.einsum("ij,ij->i", e1, h)
            valid = abs(den) > 1e-15
            inverse = np.divide(1., den, out=np.zeros(len(den)), where=valid)
            s = origin - triangles[:, 0]
            u = np.einsum("ij,ij->i", s, h) * inverse
            q = np.cross(s, e1)
            v = q @ direction * inverse
            t = np.einsum("ij,ij->i", e2, q) * inverse
            valid &= (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) & (t >= near_t) & (t <= far_t)
            indices = np.flatnonzero(valid)
            if not len(indices):
                continue
            index = int(indices[np.argmin(t[indices])])
            if best is None or t[index] < best["segmentParameter"]:
                best = {"partPath": path, "actualNativeTriangleIndex": index,
                        "actualNativeVertexIndices": part["F"][index].tolist(),
                        "segmentParameter": float(t[index]),
                        "worldPointMetres": (origin + t[index] * direction).tolist()}
        return best

    def nib_guard(self, origin, rotation):
        origin = finite_ray_array(origin, (3,), "Ray origin")
        rotation = proper_camera_rotation(rotation)
        self.assert_code()
        marker = self.parts[self.nib["partPath"]]
        vertex = self.nib["nativeVertexIndex"]
        point = marker["P"][vertex]
        direction = point - origin
        depth = float(-(direction @ rotation)[2])
        if depth <= .005:
            return -1000., None
        hit = self.first_surface(origin, direction, .005 / depth, 100 / depth)
        if hit is None:
            return -1000., None
        residual = float(np.linalg.norm(np.asarray(hit["worldPointMetres"]) - point))
        epsilon = self.nib["eligibilityEpsilonMetres"]
        eligible = (hit["partPath"] == self.nib["partPath"]
                    and hit["actualNativeTriangleIndex"] in self.incident_nib_triangles
                    and residual <= epsilon)
        value = 1000 * (epsilon - residual) if eligible else min(1000 * (hit["segmentParameter"] - 1) * np.linalg.norm(direction) - .001, -.001)
        hit.update({"actualFiniteNibVertexIndex": vertex,
                    "exactStoredLocalEquivalentVertexIndices": self.equivalent_vertices.tolist(),
                    "actualFiniteNibResidualMetres": residual,
                    "actualFiniteNibEligibilityEpsilonMetres": epsilon,
                    "actualFiniteNibIsExactNearestPositiveSurface": bool(eligible),
                    "completeNativeDenominator": len(self.parts), "GPUAcceptance": False,
                    "epoch": "sealed-current-code-CPU",
                    "sourceFeatureAssociation": "unavailable"})
        self.assert_code()
        return float(value), hit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--native-export", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, default=WEB.parent)
    parser.add_argument("--profile", type=Path, default=PROFILE)
    parser.add_argument("--rays", type=Path, required=True, help="JSON frozen-state controls: origin/rotation only; no part or input transforms")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    allowed_ray_fields = {"id", "origin", "rotation", "expectedNativeEligibility",
                          "cameraOriginInsideNativeAabbPaths"}
    request_bytes = args.rays.read_bytes()
    request_text = request_bytes.decode("utf-8")
    rows, raw_request_text_required = [], False
    for index, ray in enumerate(json.loads(request_text)["rays"]):
        reason = None
        nonfinite = request_has_nonfinite(ray)
        if not isinstance(ray, dict):
            reason = "Ray controls must be an object describing a camera on one frozen native state"
        elif unsupported := set(ray) - allowed_ray_fields:
            reason = (f"Unsupported frozen-ray fields: {', '.join(sorted(unsupported))}. "
                      "Input changes require a new complete native solve and sealed complete51/all435 export, not detached part poses")
        elif nonfinite:
            reason = "Ray requests must contain finite numeric values"
        else:
            try:
                origin = finite_ray_array(ray.get("origin"), (3,), "Ray origin")
                rotation = proper_camera_rotation(ray.get("rotation"))
            except ValueError as error:
                reason = str(error)
        row = {"id": ray.get("id") if isinstance(ray, dict) else None,
               "request": ray, "status": "refused" if reason else "pending",
               "reason": reason, "guardValue": None, "hit": None}
        if nonfinite:
            raw_request_text_required = True
            row.update(request=None, requestRepresentation="raw-packet-entry", requestIndex=index)
            if request_has_nonfinite(row["id"]):
                row["id"] = None
        if reason is None:
            row["_camera"] = (origin, rotation)
        rows.append(row)
    native, native_error = None, None
    for row in rows:
        camera = row.pop("_camera", None)
        if row["status"] == "refused":
            continue
        if native_error is not None:
            row.update(status="error", reason=native_error)
            continue
        try:
            if native is None:
                native = FrozenNativeFirstSurface(args.native_export, args.model, profile, args.code_root)
            value, hit = native.nib_guard(*camera)
            row.update(status="measured", guardValue=value, hit=hit)
        except (OSError, ValueError, KeyError, TypeError) as error:
            reason = f"Native eligibility unavailable: {error}"
            row.update(status="error", reason=reason)
            if native is None:
                native_error = reason
    result = {"producerSha256": digest(__file__), "profileSha256": digest(args.profile),
              "requestedNativeExport": str(args.native_export), "requestedModel": str(args.model),
              "rayRequestSha256": hashlib.sha256(request_bytes).hexdigest(),
              "nativeExportSha256": native.export_sha256 if native is not None else None,
              "nativeChosenInput": native.export["input"] if native is not None else None,
              "unobservedInputFields": native.export["unobservedInputFields"] if native is not None else None,
              "completeNativeDenominator": len(native.parts) if native is not None else None,
              "independentSourceExposureObligation": profile["sourceExposure"],
              "epoch": "sealed-current-code-CPU" if native is not None else "unavailable",
              "equivalentNativeVertexIndices": native.equivalent_vertices.tolist() if native is not None else None,
              "incidentNativeTriangleIndices": native.incident_nib_triangles.tolist() if native is not None else None,
              "distinctPhysicalApexCount": 1 if native is not None else None,
              "rays": rows, "GPUAcceptance": False,
              "sourceAcceptance": False, "sourceFeatureAssociation": "unavailable"}
    if raw_request_text_required:
        result["rawRayRequestText"] = request_text
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "epoch": result["epoch"], "rays": len(rows),
                      "eligibleNativeRays": sum(bool((row["hit"] or {}).get("actualFiniteNibIsExactNearestPositiveSurface")) for row in rows),
                      "refusedRays": sum(row["status"] == "refused" for row in rows),
                      "errorRays": sum(row["status"] == "error" for row in rows)}))
    return 2 if any(row["status"] != "measured" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
