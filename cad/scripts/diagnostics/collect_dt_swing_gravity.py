"""Recalibrate the seven-part/nine-instance pinion swing from completed farm STLs.

Run from the locked project environment, with --outroot RUN.out and --source-root
EXACT_SOURCE. --report may write JSON only outside that source tree. No builder,
COM, mesh-repair, build, or repository-write operation is performed.

The method preserves #859's hybrid basis: native STL centroids in the actual
assembly transforms; source analytic weight volumes for five parts and native
mesh weight volumes for the drum and brackets. This is not COM mass metrology.
"""

from __future__ import annotations

import __future__
import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib
import importlib.abc
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree
import scipy
import trimesh


COUNTS = {
    "dt-alignment-pinion": 1,
    "dt-pinion-arbor": 1,
    "dt-pinion-pivot-shaft": 1,
    "dt-pinion-bracket": 2,
    "dt-pinion-arbor-collar": 1,
    "dt-pinion-handle": 1,
    "dt-pinion-cam-pin": 2,
}
DENSITIES = {"Brass": 8500.0, "Plain Carbon Steel": 7800.0}
GRAVITY_M_S2 = 9.80665
WELD_TOLERANCE_MM = 1e-5
BLOCKED_IMPORTS = (
    "_com",
    "_session",
    "_transforms",
    "dodo",
    "pythoncom",
    "pywintypes",
    "win32com",
    "comtypes",
    "solidworks_mcp",
)
DIMENSION_SOURCES = {
    "dt-alignment-pinion": (
        "dt_alignment_pinion_spec.py",
        (
            "TEETH",
            "DIAMETRAL_PITCH",
            "PRESSURE_ANGLE_DEG",
            "FACE_WIDTH",
            "BORE_DIA",
            "CUTTER_REFERENCE_TEETH",
            "CUTTER_RADIAL_TRANSLATION_MM",
            "PITCH_TOOTH_THICKNESS_MM",
            "ROOT_ENVELOPE_DIA_MM",
            "SUPPORT_OUTSIDE_DIA_MM",
            "OUTSIDE_DIA",
            "WHOLE_DEPTH",
            "MAX_CUT_DEPTH_MM",
            "BASE_TANGENT_SPAN",
        ),
    ),
    "dt-pinion-bracket": (
        "dt_pinion_bracket_geometry.py",
        (
            "WIDTH",
            "C2C",
            "THICKNESS",
            "PIVOT_BORE",
            "ARBOR_BORE",
            "PIN_BORE",
            "PIN_SEAT",
            "PIN_DROP",
            "CROSS_HOLE_CZ",
        ),
    ),
}
CALIBRATION_NAMES = (
    "SWING_GRAVITY_NMM",
    "SWING_GRAVITY_CORNER_NMM",
    "SWING_GRAVITY_MASS_G",
    "SWING_GRAVITY_BASIS",
    "SWING_GRAVITY_FINGERPRINT",
)


def forbid_com_import(fullname):
    if any(part.startswith("build_") for part in fullname.split(".")) or any(
        fullname == name or fullname.startswith(name + ".")
        for name in BLOCKED_IMPORTS
    ):
        raise ImportError(f"COM/build import is forbidden in this analysis: {fullname}")


class NoCOM(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbid_com_import(fullname)
        return None


@contextmanager
def source_environment(root):
    """Keep source imports rooted and bytecode-free; restore the caller's settings."""
    guard = NoCOM()
    old_path = sys.path[:]
    old_bytecode = sys.dont_write_bytecode
    sys.meta_path.insert(0, guard)
    sys.path.insert(0, str(root / "cad/scripts"))
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.meta_path.remove(guard)
        sys.path[:] = old_path
        sys.dont_write_bytecode = old_bytecode


class SourceSlices:
    """Evaluate requested declarations and pure math, never a builder module."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.scripts = self.root / "cad/scripts"
        self.modules = {}
        self.hashes = {}
        self.resolving = set()

    def module(self, filename):
        if filename not in self.modules:
            path = self.scripts / filename
            data = path.read_bytes()
            self.hashes[path.relative_to(self.root).as_posix()] = hashlib.sha256(
                data
            ).hexdigest()
            tree = ast.parse(data, filename=str(path))
            definitions = {}
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        for item in ast.walk(target):
                            if isinstance(item, ast.Name):
                                definitions[item.id] = node
                elif isinstance(node, ast.AnnAssign) and isinstance(
                    node.target, ast.Name
                ):
                    definitions[node.target.id] = node
                elif isinstance(node, ast.FunctionDef):
                    definitions[node.name] = node
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        definitions[alias.asname or alias.name.split(".")[0]] = (
                            node,
                            alias,
                        )
            namespace = {
                "__builtins__": __builtins__,
                "__file__": str(path),
                "__name__": f"_dt_gravity_slice_{path.stem}",
            }
            self.modules[filename] = path, tree, definitions, namespace
        return self.modules[filename]

    def get(self, filename, name):
        path, _tree, definitions, namespace = self.module(filename)
        if name in namespace:
            return namespace[name]
        key = filename, name
        if key in self.resolving:
            raise RuntimeError(f"cyclic source dependency: {filename}:{name}")
        if name not in definitions:
            raise RuntimeError(
                f"required source declaration missing: {filename}:{name}"
            )
        self.resolving.add(key)
        try:
            entry = definitions[name]
            if isinstance(entry, tuple):
                node, alias = entry
                module_name = (
                    node.module if isinstance(node, ast.ImportFrom) else alias.name
                )
                if module_name == "_transforms":
                    if not isinstance(node, ast.ImportFrom):
                        raise RuntimeError("expected named pure _transforms import")
                    namespace[name] = self.get("_transforms.py", alias.name)
                else:
                    # Explicitly refuse cached forbidden modules as well: meta-path
                    # finders alone do not intercept imports already in sys.modules.
                    forbid_com_import(module_name)
                    standard = module_name in {"math", "itertools", "typing"}
                    if not standard:
                        expected = self.scripts / (
                            module_name.replace(".", "/") + ".py"
                        )
                        if not expected.is_file():
                            raise RuntimeError(
                                f"required source module missing: {expected}"
                            )
                    module = importlib.import_module(module_name)
                    if (
                        not standard
                        and Path(module.__file__).resolve() != expected.resolve()
                    ):
                        raise RuntimeError(
                            f"wrong source tree for {module_name}: {module.__file__}"
                        )
                    namespace[name] = (
                        getattr(module, alias.name)
                        if isinstance(node, ast.ImportFrom)
                        else module
                    )
            else:
                dependencies = {
                    item.id
                    for item in ast.walk(entry)
                    if isinstance(item, ast.Name)
                    and isinstance(item.ctx, ast.Load)
                    and item.id in definitions
                    and item.id != name
                }
                for dependency in sorted(dependencies):
                    self.get(filename, dependency)
                fragment = ast.Module(body=[entry], type_ignores=[])
                exec(
                    compile(
                        fragment,
                        str(path),
                        "exec",
                        flags=__future__.annotations.compiler_flag,
                        dont_inherit=True,
                    ),
                    namespace,
                )
            return namespace[name]
        finally:
            self.resolving.remove(key)

    def values(self, filename, names):
        return {name: self.get(filename, name) for name in names}

    def export_units(self):
        path, _tree, definitions, _namespace = self.module("_preferences.py")
        exporter_path, tree, _definitions, _namespace = self.module("_part_save.py")

        def literal(name):
            return ast.literal_eval(definitions[name].value)

        call = definitions["STL_EXPORT_PREFERENCES"].value
        if not isinstance(call, ast.Call):
            raise RuntimeError(f"STL export preference declaration changed: {path}")
        dictionaries = {item.arg: item.value for item in call.keywords}

        def setting(group, name):
            dictionary = dictionaries[group]
            if not isinstance(dictionary, ast.Dict):
                raise RuntimeError(f"STL export {group} is not a literal dictionary")
            for key, value in zip(dictionary.keys, dictionary.values, strict=True):
                if isinstance(key, ast.Name) and key.id == name:
                    return ast.literal_eval(value)
            raise RuntimeError(f"missing source STL setting: {name}")

        if (
            literal("PREF_STL_UNITS") != 211
            or setting("integers", "PREF_STL_UNITS") != 0
        ):
            raise RuntimeError(
                "source does not declare STL swMM; no unit guessing allowed"
            )
        if (
            literal("TOGGLE_STL_NO_TRANSLATE") != 71
            or setting("toggles", "TOGGLE_STL_NO_TRANSLATE") is not True
        ):
            raise RuntimeError("source STL export does not preserve part-local origin")
        exporter = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.AsyncFunctionDef)
                and node.name == "export_part_stl"
            ),
            None,
        )
        if exporter is None or not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "enforce_preferences"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Name)
            and node.args[1].id == "STL_EXPORT_PREFERENCES"
            for node in ast.walk(exporter)
        ):
            raise RuntimeError(
                f"native STL exporter no longer enforces declared preferences: {exporter_path}"
            )
        return {
            "coordinate_unit": "mm",
            "scale_to_mm": 1.0,
            "origin_preserved": True,
            "source": "cad/scripts/_preferences.py",
            "preference": "PREF_STL_UNITS=211, applied value 0 (swMM)",
            "declaration_line": call.lineno,
        }


def dimension_fingerprint(reader):
    """Same governing-dimension reader for the collector and frozen-basis test."""
    dimensions = {
        stem: reader.values(filename, names)
        for stem, (filename, names) in DIMENSION_SOURCES.items()
    }
    # The stock cutter's off-centre root arc has a radial envelope, not one
    # concentric ROOT_DIA. Freeze both actual bounds as numeric report fields.
    drum = dimensions["dt-alignment-pinion"]
    root_min, root_max = drum.pop("ROOT_ENVELOPE_DIA_MM")
    drum["ROOT_MIN_DIA_MM"] = root_min
    drum["ROOT_MAX_DIA_MM"] = root_max
    return dimensions


class MeshTopologyError(RuntimeError):
    def __init__(self, path, *, watertight, winding_consistent):
        self.watertight = bool(watertight)
        self.winding_consistent = bool(winding_consistent)
        failures = []
        if not self.watertight:
            failures.append("open or non-manifold edges")
        if not self.winding_consistent:
            failures.append("inconsistent winding")
        super().__init__(
            f"native STL watertight={self.watertight} "
            f"winding_consistent={self.winding_consistent}: {path}: "
            + "; ".join(failures)
        )


def weld_vertices(mesh):
    """Union float32 seam partners, retaining original representative coordinates.

    KD-tree radius pairs cross rounding-grid boundaries. Only vertex indices
    change: no coordinate averaging, hole filling, face removal or winding fix.
    process=False is essential, including on construction of the welded mesh.
    """
    vertices = np.asarray(mesh.vertices)
    parent = np.arange(len(vertices))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    pairs = cKDTree(vertices).query_pairs(WELD_TOLERANCE_MM, output_type="ndarray")
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots = np.fromiter((find(i) for i in range(len(vertices))), dtype=np.int64)
    representatives, indices = np.unique(roots, return_inverse=True)
    return trimesh.Trimesh(
        vertices=vertices[representatives],
        faces=indices[np.asarray(mesh.faces)],
        process=False,
        validate=False,
    )


def read_mesh(path):
    path = Path(path)
    data = path.read_bytes()
    mesh = trimesh.load_mesh(io.BytesIO(data), file_type="stl", process=False)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise RuntimeError(f"not a nonempty triangle mesh: {path}")
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(mesh.face_normals).all():
        raise RuntimeError(f"nonfinite native STL geometry: {path}")
    input_vertices = len(mesh.vertices)
    input_faces = len(mesh.faces)
    mesh = weld_vertices(mesh)
    watertight = bool(mesh.is_watertight)
    winding = bool(mesh.is_winding_consistent)
    if not watertight or not winding:
        raise MeshTopologyError(path, watertight=watertight, winding_consistent=winding)
    volume = float(mesh.volume)
    com = np.asarray(mesh.center_mass, dtype=float)
    if (
        not math.isfinite(volume)
        or volume <= 0.0
        or com.shape != (3,)
        or not np.isfinite(com).all()
    ):
        raise RuntimeError(f"native STL has invalid positive volume/COM: {path}")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "native_mesh_volume_mm3": volume,
        "local_mesh_com_mm": com.tolist(),
        "input_vertices": input_vertices,
        "welded_vertices": int(len(mesh.vertices)),
        "input_faces": input_faces,
        "faces": int(len(mesh.faces)),
        "watertight": watertight,
        "winding_consistent": winding,
        "weld_tolerance_mm": WELD_TOLERANCE_MM,
        "weld_method": "scipy cKDTree query_pairs + union-find; first vertex retained",
    }


def calibration_report(outroot, source_root):
    """Collect without altering the frozen source calibration or its measurement guard."""
    outroot = Path(outroot).resolve(strict=True)
    source_root = Path(source_root).resolve(strict=True)
    missing = [
        str(outroot / "stl" / f"{stem}.STL")
        for stem in COUNTS
        if not (outroot / "stl" / f"{stem}.STL").is_file()
    ]
    if missing:
        raise RuntimeError("missing required farm STLs: " + ", ".join(missing))
    with source_environment(source_root):
        return _calibration_report(outroot, SourceSlices(source_root))


def _calibration_report(outroot, reader):
    units = reader.export_units()
    geometry = reader.values(
        "build_dt_drive_train_assembly.py",
        (
            "APINION_X",
            "APINION_Y",
            "APINION_Z_FRONT",
            "PIVOT_X",
            "PIVOT_Y",
            "PIVOT_SHAFT_Z0",
            "HANDLE_Z",
            "HANDLE_ROWS",
            "ARBOR_Z0",
            "ARBOR_ROWS",
            "ARBOR_COLLAR_Z0",
            "IDENTITY",
            "STRAP_ORIGIN_Z",
            "STRAP_ROWS",
            "TORQUE_SHAFT_ROWS",
            "_FPIN_ORG",
            "_STRAP_MID_Z",
            "FPIN_ROWS",
            "_PHI_ENG",
            *CALIBRATION_NAMES,
        ),
    )
    g = geometry
    phi = float(g["_PHI_ENG"])
    if not math.isfinite(phi) or not 0.01 < phi < math.radians(10.0):
        raise RuntimeError(f"source engage angle outside native design guard: {phi}")
    pivot = np.array([g["PIVOT_X"], g["PIVOT_Y"], 0.0], dtype=float)
    instances = {
        "dt-alignment-pinion": [
            (
                "drum",
                [g["APINION_X"], g["APINION_Y"], g["APINION_Z_FRONT"]],
                g["IDENTITY"],
            )
        ],
        "dt-pinion-arbor": [
            ("arbor", [g["APINION_X"], g["APINION_Y"], g["ARBOR_Z0"]], g["ARBOR_ROWS"])
        ],
        "dt-pinion-pivot-shaft": [
            (
                "torque-shaft",
                [g["PIVOT_X"], g["PIVOT_Y"], g["PIVOT_SHAFT_Z0"]],
                g["TORQUE_SHAFT_ROWS"],
            )
        ],
        "dt-pinion-bracket": [
            (tag, [g["PIVOT_X"], g["PIVOT_Y"], z], g["STRAP_ROWS"])
            for tag, z in zip(("front", "back"), g["STRAP_ORIGIN_Z"], strict=True)
        ],
        "dt-pinion-arbor-collar": [
            (
                "collar",
                [g["APINION_X"], g["APINION_Y"], g["ARBOR_COLLAR_Z0"]],
                g["ARBOR_ROWS"],
            )
        ],
        "dt-pinion-handle": [
            (
                "crossrod",
                [g["APINION_X"], g["APINION_Y"], g["HANDLE_Z"]],
                g["HANDLE_ROWS"],
            )
        ],
        "dt-pinion-cam-pin": [
            (tag, [*g["_FPIN_ORG"], z], g["FPIN_ROWS"])
            for tag, z in zip(("front", "back"), g["_STRAP_MID_Z"], strict=True)
        ],
    }
    a = reader.values("build_dt_pinion_arbor.py", ("V_TOTAL",))
    s = reader.values(
        "build_dt_pinion_pivot_shaft.py", ("V_SHAFT", "V_CAP", "_pin_hole_removed")
    )
    c = reader.values("build_dt_pinion_arbor_collar.py", ("V_COLLAR", "V_PIN_HOLE"))
    h = reader.values("build_dt_pinion_handle.py", ("V_ROD",))
    f = reader.values("build_dt_pinion_cam_pin.py", ("V_PIN", "V_CAP"))
    analytic = {
        "dt-pinion-arbor": (a["V_TOTAL"], "V_TOTAL"),
        "dt-pinion-pivot-shaft": (
            s["V_SHAFT"] + 2 * s["V_CAP"] - 2 * s["_pin_hole_removed"](),
            "V_SHAFT + 2*V_CAP - 2*_pin_hole_removed()",
        ),
        "dt-pinion-arbor-collar": (
            c["V_COLLAR"] - c["V_PIN_HOLE"],
            "V_COLLAR - V_PIN_HOLE",
        ),
        "dt-pinion-handle": (h["V_ROD"], "V_ROD"),
        "dt-pinion-cam-pin": (f["V_PIN"] + f["V_CAP"], "V_PIN + V_CAP"),
    }
    frozen = g["SWING_GRAVITY_BASIS"]
    if set(frozen) != set(COUNTS):
        raise RuntimeError("source gravity basis is not the existing seven-part scope")
    parts, mass_g, mesh_mass_g = {}, [0.0, 0.0], [0.0, 0.0]
    moments = np.zeros((2, 2), dtype=float)  # density case, parked/engaged
    mesh_moments = np.zeros((2, 2), dtype=float)
    cp, sp = math.cos(phi), math.sin(phi)
    for stem, count in COUNTS.items():
        material = reader.get("build_" + stem.replace("-", "_") + ".py", "MATERIAL")
        density = DENSITIES.get(material)
        corner_density = 8800.0 if material == "Brass" else density
        if density is None or count != frozen[stem][0]:
            raise RuntimeError(
                f"source count/material changed outside calibration scope: {stem}"
            )
        row = read_mesh(outroot / "stl" / f"{stem}.STL")
        weight_volume = (
            float(analytic[stem][0])
            if stem in analytic
            else row["native_mesh_volume_mm3"]
        )
        if not math.isfinite(weight_volume) or weight_volume <= 0.0:
            raise RuntimeError(
                f"invalid source analytic basis volume: {stem}: {weight_volume}"
            )
        row.update(
            {
                "count": count,
                "material": material,
                "density_kg_m3": density,
                "corner_density_kg_m3": corner_density,
                "weight_volume_mm3": weight_volume,
                "weight_volume_kind": "source analytic formula"
                if stem in analytic
                else "native exported STL",
                "weight_volume_expression": analytic[stem][1]
                if stem in analytic
                else "mesh.volume (mm^3)",
                "frozen_basis_volume_mm3": frozen[stem][1],
                "mesh_minus_weight_volume_mm3": row["native_mesh_volume_mm3"]
                - weight_volume,
                "nominal_mass_g_per_instance": weight_volume * density * 1e-6,
                "corner_mass_g_per_instance": weight_volume * corner_density * 1e-6,
                "instances": [],
            }
        )
        if len(instances[stem]) != count:
            raise RuntimeError(f"placement count disagrees with source basis: {stem}")
        for label, origin, rotation in instances[stem]:
            origin = np.asarray(origin, dtype=float)
            rotation = np.asarray(rotation, dtype=float)
            if (
                origin.shape != (3,)
                or rotation.shape != (3, 3)
                or not np.isfinite(origin).all()
                or not np.isfinite(rotation).all()
            ):
                raise RuntimeError(f"invalid source placement: {stem}:{label}")
            if not np.allclose(
                rotation @ rotation.T, np.eye(3), rtol=0.0, atol=1e-10
            ) or not math.isclose(
                float(np.linalg.det(rotation)), 1.0, rel_tol=0.0, abs_tol=1e-10
            ):
                raise RuntimeError(
                    f"source placement is not a proper rotation: {stem}:{label}"
                )
            parked = origin + np.asarray(row["local_mesh_com_mm"]) @ rotation
            relative = parked - pivot
            engaged = pivot + np.array(
                [
                    relative[0] * cp - relative[1] * sp,
                    relative[0] * sp + relative[1] * cp,
                    relative[2],
                ]
            )
            arms = pivot[0] - np.array([parked[0], engaged[0]])
            if not np.isfinite(parked).all() or not np.isfinite(engaged).all():
                raise RuntimeError(
                    f"nonfinite transformed mesh centroid: {stem}:{label}"
                )
            contribution = np.array(
                [
                    weight_volume * rho * 1e-9 * GRAVITY_M_S2 * arms
                    for rho in (density, corner_density)
                ]
            )
            mesh_contribution = contribution * (
                row["native_mesh_volume_mm3"] / weight_volume
            )
            moments += contribution
            mesh_moments += mesh_contribution
            for case, rho in enumerate((density, corner_density)):
                mass_g[case] += weight_volume * rho * 1e-6
                mesh_mass_g[case] += row["native_mesh_volume_mm3"] * rho * 1e-6
            row["instances"].append(
                {
                    "label": label,
                    "origin_mm": origin.tolist(),
                    "rotation_rows": rotation.tolist(),
                    "parked_world_com_mm": parked.tolist(),
                    "engaged_world_com_mm": engaged.tolist(),
                    "closing_moments_nmm": {
                        "nominal": contribution[0].tolist(),
                        "brass_8800_corner": contribution[1].tolist(),
                    },
                }
            )
        parts[stem] = row
    fingerprint = dimension_fingerprint(reader)
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(reader.root) and path.suffix == ".py":
                reader.hashes[path.relative_to(reader.root).as_posix()] = (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                )
    for path in sorted((reader.root / "cad/config").rglob("*.yaml")):
        reader.hashes[path.relative_to(reader.root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    if (
        not np.isfinite(moments).all()
        or not np.isfinite(mesh_moments).all()
        or not all(math.isfinite(v) and v > 0 for v in (*mass_g, *mesh_mass_g))
    ):
        raise RuntimeError("nonfinite gravity/mass aggregate")
    return {
        "schema_version": 1,
        "method": "native-exported STL centroids with source assembly transforms and hybrid analytic/mesh volume weights; not native COM mass measurements",
        "method_provenance": {
            "original_commit": "03b51bce25baf063402968e56359baff900b229a",
            "main_equivalent_commit": "964b1229f",
            "original_mesh_baseline": "c486 warm integration; post-c486 analytic weight updates (#858/#860)",
            "collector_origin": "external inch_train_swing_gravity.py (359 lines), ported to this maintained diagnostic",
        },
        "outroot": str(outroot),
        "source_root": str(reader.root),
        "provenance_caveat": "STL bytes carry no source commit or unit metadata. Source hashes and exporter settings describe --source-root, not proof those sources produced --outroot. Confirm governing geometry/materials match the completed farm artifacts before installing calibration.",
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "stl_units": units,
        "gravity_m_s2": GRAVITY_M_S2,
        "pose_order": ["parked", "engaged"],
        "density_case_order": ["nominal_brass_8500", "brass_8800_corner"],
        "pivot_xy_mm": pivot[:2].tolist(),
        "engage_angle_rad": phi,
        "engage_angle_deg": math.degrees(phi),
        "parts": parts,
        "closing_moments_nmm": moments.tolist(),
        "total_mass_g": mass_g,
        "native_mesh_only_comparison": {
            "closing_moments_nmm": mesh_moments.tolist(),
            "total_mass_g": mesh_mass_g,
        },
        "recommended_calibration": {
            "SWING_GRAVITY_NMM": moments[0].tolist(),
            "SWING_GRAVITY_CORNER_NMM": moments[1].tolist(),
            "SWING_GRAVITY_MASS_G": mass_g[0],
            "SWING_GRAVITY_BASIS": {
                stem: [row["count"], row["weight_volume_mm3"], row["density_kg_m3"]]
                for stem, row in parts.items()
            },
            "SWING_GRAVITY_FINGERPRINT": fingerprint,
        },
        "frozen_source_calibration_unchanged": {
            name: g[name] for name in CALIBRATION_NAMES
        },
        "source_sha256": dict(sorted(reader.hashes.items())),
        "versions": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "trimesh": trimesh.__version__,
        },
        "scope": "existing seven stems/nine instances only; no omitted-hardware expansion or native interference/spring-guard certification",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outroot", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve(strict=True)
    report_path = args.report.resolve() if args.report else None
    if report_path and report_path.is_relative_to(source_root):
        raise RuntimeError(
            "report must be outside the source tree; no repository writes"
        )
    report = calibration_report(args.outroot, source_root)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if report_path:
        report_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ImportError,
        RuntimeError,
        ValueError,
        KeyError,
        AttributeError,
        TypeError,
    ) as exc:
        raise SystemExit(f"pinion swing gravity analysis refused: {exc}") from exc
