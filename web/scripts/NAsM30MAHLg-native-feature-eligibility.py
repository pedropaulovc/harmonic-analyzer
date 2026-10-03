#!/usr/bin/env python3
"""Intro native-feature support and finite-nib eligibility, CPU only.

The exact stored local POSITION equivalence class supplies incident facets, not
additional calibration points. A full435 first-surface result remains conditional
on the sealed chosen input/export epoch and does not identify the source nib.
Operation requires a fresh native export and refuses any native code differing
from --code-root. Historical snapshots are not a current eligibility authority.
"""
import argparse
import hashlib
import json
import mmap
import struct
from pathlib import Path

import numpy as np

WEB = Path(__file__).resolve().parents[1]
PROFILE = WEB / "content" / "NAsM30MAHLg.calibration-eligibility.json"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
        self.profile = profile
        self.nib = profile["finiteNib"]
        source_identity = self.export.get("modelSourceSha256", self.export["modelSha256"])
        if source_identity != profile["modelSha256"]:
            raise ValueError("Posed export does not identify the original native source geometry")
        if (self.export["nativeDrawableDenominator"] != self.nib["requiredNativeDrawableCount"]
                or self.export["springDrawableCount"] != self.nib["requiredSpringDrawableCount"]
                or len(self.export["unobservedInputFields"]) != 51
                or not self.export.get("inputMechanismAndAll435ArraysFrozenAsOneState")
                or self.export.get("partOverrides")):
            raise ValueError("Finite nib requires one complete chosen51/all435/21-spring native state, without detached overrides")
        hashes = self.export["codeHashes"]
        snapshots = self.export["actuallyExecutedImmutableNativeSourceSnapshots"]
        closure_hashes = {row["relativePath"]: row["sha256"] for row in snapshots}
        if not snapshots or len(closure_hashes) != len(snapshots) or any(
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
        for name, dtype in (("positions", "<f8"), ("indices", "<u4")):
            entry = self.export["geometry"][name]
            if not isinstance(entry, dict):
                raise ValueError("Complete posed all435 arrays are unavailable; rigid geometry plus spring shader payload is not first-surface evidence")
            path = self.export_path.parent / entry["path"]
            if digest(path) != entry["sha256"]:
                raise ValueError("Posed native array differs from its sealed export")
            arrays[name] = np.memmap(path, dtype=dtype, mode="r")
        for row in self.export["census"]:
            path = row["path"]
            if path in self.parts:
                raise ValueError("Duplicate actual native primitive path")
            p_offset, f_offset = row["positionByteOffset"] // 8, row["indexByteOffset"] // 4
            positions = arrays["positions"][p_offset:p_offset + row["vertexCount"] * 3].reshape(-1, 3)
            faces = arrays["indices"][f_offset:f_offset + row["indexCount"]].reshape(-1, 3)
            self.parts[path] = {"P": positions, "F": faces, "M": np.asarray(row["matrixWorld"]).reshape(4, 4, order="F"),
                                "visible": row["visibleByNativeGraph"]}
            self.parts[path]["bounds"] = (positions.min(axis=0), positions.max(axis=0))
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

    def first_surface(self, origin, direction, matrices, near_t, far_t):
        origin, direction = np.asarray(origin), np.asarray(direction)
        best = None
        nonzero = abs(direction) > 1e-15
        direction_inverse = np.divide(1., direction, out=np.zeros(3), where=nonzero)
        for path, part in self.parts.items():
            if not part["visible"]:
                continue
            positions = part["P"]
            if path in matrices:
                local = np.c_[positions, np.ones(len(positions))] @ np.linalg.inv(part["M"]).T
                positions = (local @ np.asarray(matrices[path]).T)[:, :3]
            lo, hi = (positions.min(axis=0), positions.max(axis=0)) if path in matrices else part["bounds"]
            if np.any(~nonzero & ((origin < lo) | (origin > hi))):
                continue
            aa, bb = (lo - origin) * direction_inverse, (hi - origin) * direction_inverse
            entry = max(np.where(nonzero, np.minimum(aa, bb), -np.inf).max(), near_t)
            exit_t = min(np.where(nonzero, np.maximum(aa, bb), np.inf).min(), far_t)
            if entry > exit_t or best is not None and entry > best["segmentParameter"]:
                continue
            if path in matrices or "triangleData" not in part:
                triangles = positions[part["F"]]
                e1, e2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
                if path not in matrices:
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

    def nib_guard(self, origin, rotation, matrices=None):
        self.assert_code()
        matrices = {} if matrices is None else matrices
        allowed = {f"harmonic-analyzer/pen/{name}-1" for name in ("pen-v-block", "pen-frame", "pen-marker", "pen-set-screw")}
        if set(matrices) - allowed:
            raise ValueError("Input changes require a new complete native solve, not piecewise pose changes")
        marker = self.parts[self.nib["partPath"]]
        vertex = self.nib["nativeVertexIndex"]
        point = marker["P"][vertex]
        if self.nib["partPath"] in matrices:
            local = np.linalg.inv(marker["M"]) @ np.r_[point, 1]
            point = (np.asarray(matrices[self.nib["partPath"]]) @ local)[:3]
        direction = point - origin
        depth = float(-(direction @ rotation)[2])
        if depth <= .005:
            return -1000., None
        hit = self.first_surface(origin, direction, matrices, .005 / depth, 100 / depth)
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
    parser.add_argument("--rays", type=Path, required=True, help="JSON controls: origin/rotation, optional supported matrices")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native = FrozenNativeFirstSurface(args.native_export, args.model, json.loads(args.profile.read_text()), args.code_root)
    rows = []
    for ray in json.loads(args.rays.read_text())["rays"]:
        value, hit = native.nib_guard(np.asarray(ray["origin"]), np.asarray(ray["rotation"]), ray.get("matrices"))
        rows.append({"id": ray["id"], "guardValue": value, "hit": hit})
    result = {"producerSha256": digest(__file__), "profileSha256": digest(args.profile),
              "nativeExportSha256": native.export_sha256,
              "nativeChosenInput": native.export["input"],
              "independentSourceExposureObligation": native.profile["sourceExposure"],
              "epoch": "sealed-current-code-CPU",
              "equivalentNativeVertexIndices": native.equivalent_vertices.tolist(),
              "incidentNativeTriangleIndices": native.incident_nib_triangles.tolist(),
              "distinctPhysicalApexCount": 1, "rays": rows, "GPUAcceptance": False,
              "sourceAcceptance": False, "sourceFeatureAssociation": "unavailable"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "epoch": result["epoch"], "rays": len(rows),
                      "eligibleNativeRays": sum(bool((row["hit"] or {}).get("actualFiniteNibIsExactNearestPositiveSurface")) for row in rows)}))


if __name__ == "__main__":
    main()
