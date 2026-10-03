"""Native-support camera fitting and frozen-state ray refusal at real entry points.

Requires numpy, scipy, opencv-python-headless and the original raw2280 GLB:
  INTRO_RAW_NATIVE_MODEL_PATH=/private/raw/harmonic-analyzer.glb \
    python web/scripts/test_intro_feature_eligibility.py

History controls select exact materialized git revisions, never edited predicates.
INTRO_STATIC_PRODUCER_PATH selects the static camera producer (f20571861).
INTRO_NATIVE_FEATURE_PRODUCER_PATH selects native ray eligibility (7d89e1bf7).
Missing or mismatched raw bytes fail, never a green skip. The CLI error/refusal
controls do not depend on an unreconstructible private full435 checkpoint; actual
positive first-surface proof requires a separately sealed native export.
"""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
WEB = HERE.parent


def load_script(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntroNativeFeatureEligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw_path = os.environ.get("INTRO_RAW_NATIVE_MODEL_PATH")
        if not raw_path:
            raise RuntimeError("INTRO_RAW_NATIVE_MODEL_PATH is required and must identify the actual original raw2280 GLB; optimized transport is not a substitute")
        cls.production = load_script(
            Path(os.environ.get("INTRO_STATIC_PRODUCER_PATH", HERE / "NAsM30MAHLg-calibrate-static.py")),
            "intro_static_production_under_test",
        )
        cls.feature = load_script(HERE / "NAsM30MAHLg-native-feature-eligibility.py", "intro_real_native_feature_support")
        cls.fit_source = load_script(HERE / "fit-source.py", "intro_real_camera_projector")
        profile = json.loads((WEB / "content" / "NAsM30MAHLg.calibration-eligibility.json").read_text())
        local, _ = cls.feature.stored_primitive(
            Path(raw_path), profile["finiteNib"]["partPath"],
            profile["finiteNib"]["primitiveIndex"], profile["modelSha256"],
        )
        cls.apex_indices = (124, 126, 130, 133, 136, 139)
        # An independent proper rigid native pose preserves these exact stored
        # positions and their rank; no fitted/deformed435 graph is fabricated.
        angle = math.radians(23)
        cls.rotation = np.array([[math.cos(angle), 0, math.sin(angle)],
                                 [0, 1, 0],
                                 [-math.sin(angle), 0, math.cos(angle)]])
        cls.translation = np.array([0.02, 0.36, -0.14])
        cls.world = local.astype(float) @ cls.rotation.T + cls.translation
        unique = np.unique(local.astype(float), axis=0)
        cls.distinct = unique[np.arange(8) * 8] @ cls.rotation.T + cls.translation
        cls.eye = np.array([0.04, 0.41, -0.60])
        cls.focal = 1200.0
        # CV camera rotation is identity, so the independent perspective law is
        # x/y divided by positive z. The native camera-to-world is the proper
        # diag(1,-1,-1) convention. Never call fit_source.project to create data.
        cls.initial = np.r_[np.zeros(3), -cls.eye, math.log(cls.focal)]

    def frame_and_points(self, fit_points, check_points):
        points, landmarks = {}, []
        for role, coordinates in (("fit", fit_points), ("check", check_points)):
            for index, xyz in enumerate(coordinates):
                key = f"{role}-native-feature-{index}"
                points[key] = np.asarray(xyz, dtype=float)
                camera_point = points[key] - self.eye
                self.assertGreater(camera_point[2], 0.005)
                pixel = [960 + self.focal * camera_point[0] / camera_point[2],
                         540 + self.focal * camera_point[1] / camera_point[2]]
                landmarks.append({"anchorId": key, "role": role, "pixel": pixel,
                                  "status": "observed", "method": "manual", "uncertaintyPx": 1.0})
        return {"landmarks": landmarks}, points

    def reject_before_optimization(self, frame, points):
        original = copy.deepcopy(frame)
        with patch.object(self.production, "least_squares", side_effect=AssertionError(
                "An ineligible native-support camera reached the optimizer")):
            camera = self.production.fit_candidate(frame, points, self.initial, self.fit_source)
        self.assertIsNone(camera, "Repeated actual native support must not produce a camera candidate")
        self.assertEqual(frame, original, "Rejecting support must not rewrite independent source roles or pixels")

    def test_six_named_seam_vertices_are_one_physical_apex(self):
        fit_points = self.world[list(self.apex_indices)]
        self.assertTrue(np.all(fit_points == fit_points[0]))
        frame, points = self.frame_and_points(fit_points, self.distinct[6:])
        self.reject_before_optimization(frame, points)

    def test_check_support_coincident_with_fit_is_not_independent(self):
        frame, points = self.frame_and_points(self.distinct[:6], [self.distinct[0], self.distinct[7]])
        self.reject_before_optimization(frame, points)

    def test_distinct_rank_three_native_support_fits_independent_camera(self):
        coordinates = self.distinct[:6]
        self.assertEqual(np.linalg.matrix_rank(coordinates - coordinates.mean(axis=0), tol=1e-6), 3)
        frame, points = self.frame_and_points(coordinates, self.distinct[6:])
        original = copy.deepcopy(frame)
        camera = self.production.fit_candidate(frame, points, self.initial, self.fit_source)
        self.assertIsNotNone(camera, "Actual distinct noncoplanar native support must retain a reachable camera family")
        self.assertLess(camera["fitMaxPx"], 1e-5)
        self.assertLess(camera["heldOutMaxPx"], 1e-5)
        # Check the held-out prediction using independent camera-space algebra,
        # not the production projector or copies of reported residual fields.
        quaternion = np.asarray(camera["quaternion"])
        x, y, z, w = quaternion
        rotation = np.array([
            [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
            [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
            [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
        ])
        focal = 1080 / (2 * math.tan(math.radians(camera["verticalFovDegrees"]) / 2))
        for point in frame["landmarks"]:
            if point["role"] != "check":
                continue
            native_camera = (points[point["anchorId"]] - camera["positionMetres"]) @ rotation
            self.assertLess(native_camera[2], -0.005)
            prediction = np.array([960 + focal * native_camera[0] / -native_camera[2],
                                   540 - focal * native_camera[1] / -native_camera[2]])
            self.assertLess(np.linalg.norm(prediction - point["pixel"]), 1e-5)
        self.assertEqual(frame, original)


class SealedNativeRayRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw_path = os.environ.get("INTRO_RAW_NATIVE_MODEL_PATH")
        if not raw_path:
            raise RuntimeError("INTRO_RAW_NATIVE_MODEL_PATH must identify the actual original raw2280 GLB")
        cls.producer_path = Path(os.environ.get(
            "INTRO_NATIVE_FEATURE_PRODUCER_PATH",
            HERE / "NAsM30MAHLg-native-feature-eligibility.py",
        ))
        cls.feature = load_script(cls.producer_path, "intro_sealed_native_ray_production")
        cls.raw_path = Path(raw_path)
        cls.profile_path = WEB / "content" / "NAsM30MAHLg.calibration-eligibility.json"
        cls.profile = json.loads(cls.profile_path.read_text())
        if cls.feature.digest(cls.raw_path) != cls.profile["modelSha256"]:
            raise RuntimeError("CLI controls require actual original raw2280 bytes, not optimized transport")
        cls.marker_path = cls.profile["finiteNib"]["partPath"]
        # Authored native CPU control from the original HOLD complete51/all435
        # packet, not a source observation or a replacement geometry fixture.
        cls.ray = {
            "id": "current-apex-facet-normal-112",
            "origin": [-0.02838028776541817, 0.3383387434680341, -0.13525474965557324],
            "rotation": [
                [0.4221054454084309, -0.6786858386625051, -0.6010095884056447],
                [0., 0.6629659139080231, -0.7486495822453252],
                [0.9065467406353356, 0.3160090653684987, 0.2798415223807535],
            ],
        }

    def run_cli(self, rays, export_content=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_path, output_path = root / "rays.json", root / "result.json"
            export_path = root / "missing-native-export.json"
            if export_content is not None:
                export_path.write_text(export_content)
            request_path.write_text(json.dumps({"rays": rays}))
            completed = subprocess.run([
                sys.executable, str(self.producer_path),
                "--model", str(self.raw_path),
                "--native-export", str(export_path),
                "--profile", str(self.profile_path),
                "--rays", str(request_path),
                "--output", str(output_path),
            ], capture_output=True, text=True)
            self.assertTrue(output_path.is_file(), completed.stderr)
            return completed.returncode, json.loads(output_path.read_text())

    def assert_no_native_claim(self, returncode, result):
        self.assertNotEqual(returncode, 0)
        self.assertIsNone(result["nativeChosenInput"])
        self.assertIsNone(result["completeNativeDenominator"])
        self.assertFalse(result["GPUAcceptance"])
        self.assertFalse(result["sourceAcceptance"])

    def test_cli_detached_marker_and_occluder_refused_before_export_access(self):
        occluder = "harmonic-analyzer/pen/pen-frame-1"
        matrix = np.eye(4)
        matrix[0, 3] = 1.
        rays = [dict(copy.deepcopy(self.ray), id=f"detached-{index}",
                     matrices={path: matrix.tolist()})
                for index, path in enumerate((self.marker_path, occluder))]
        returncode, result = self.run_cli(rays)
        self.assert_no_native_claim(returncode, result)
        self.assertEqual(len(result["rays"]), len(rays))
        for request, row in zip(rays, result["rays"]):
            self.assertEqual(row["id"], request["id"])
            self.assertEqual(row["request"], request)
            self.assertEqual(row["status"], "refused")
            self.assertIsInstance(row["reason"], str)
            self.assertIsNone(row["guardValue"])
            self.assertIsNone(row["hit"])

    def test_cli_null_empty_and_stale_override_fields_are_not_frozen_rays(self):
        rays = [dict(copy.deepcopy(self.ray), id=f"invalid-matrices-{index}",
                     matrices=matrices) for index, matrices in enumerate((None, {}))]
        rays.append(dict(copy.deepcopy(self.ray), id="stale-physical-body-variant",
                         partOverrides=[{"partPath": self.marker_path,
                                         "worldPositionMetres": [1., 0., 0.]}]))
        rays.append(dict(copy.deepcopy(self.ray), id="unsealed-whole-input",
                         input={"pen": {"heightM": 1.}}))
        returncode, result = self.run_cli(rays)
        self.assert_no_native_claim(returncode, result)
        self.assertEqual(len(result["rays"]), len(rays))
        for request, row in zip(rays, result["rays"]):
            self.assertEqual(row["request"], request)
            self.assertEqual(row["status"], "refused")
            self.assertIsInstance(row["reason"], str)
            self.assertIsNone(row["guardValue"])
            self.assertIsNone(row["hit"])

    def test_no_override_ray_requires_real_sealed_native_assets(self):
        for export_content in (None, "null", "{}"):
            with self.subTest(export_content=export_content):
                returncode, result = self.run_cli([self.ray], export_content)
                self.assert_no_native_claim(returncode, result)
                row = result["rays"][0]
                self.assertEqual(row["request"], self.ray)
                self.assertEqual(row["status"], "error")
                self.assertIsInstance(row["reason"], str)
                self.assertIsNone(row["guardValue"])
                self.assertIsNone(row["hit"])
                self.assertEqual(row["id"], self.ray["id"])

    def test_mixed_packet_preserves_refusal_despite_missing_native_assets(self):
        detached = dict(copy.deepcopy(self.ray), id="detached-marker", matrices=None)
        returncode, result = self.run_cli([self.ray, detached])
        self.assert_no_native_claim(returncode, result)
        self.assertEqual([row["status"] for row in result["rays"]], ["error", "refused"])
        self.assertEqual([row["request"] for row in result["rays"]], [self.ray, detached])
        for row in result["rays"]:
            self.assertIsInstance(row["reason"], str)
            self.assertIsNone(row["guardValue"])
            self.assertIsNone(row["hit"])

    def test_nested_malformed_export_preserves_mixed_request_error_records(self):
        common = load_script(HERE / "compact-source-common.py", "intro_native_metadata_contract")
        track = json.loads((WEB / "content" / "NAsM30MAHLg.source-track.json").read_text())
        chosen_input = next(view["input"] for frame in track["frames"]
                            for view in frame["views"] if isinstance(view.get("input"), dict))
        native_path = WEB / "src" / "scene.ts"
        native_sha = self.feature.digest(native_path)
        # Deliberately incomplete invalid export metadata, using the genuine
        # public chosen input/field catalogue/current source identity. There are
        # no fabricated posed arrays, census rows, or positive geometry claims.
        header = {
            "modelSha256": self.profile["modelSha256"],
            "nativeDrawableDenominator": self.profile["finiteNib"]["requiredNativeDrawableCount"],
            "springDrawableCount": self.profile["finiteNib"]["requiredSpringDrawableCount"],
            "input": chosen_input, "unobservedInputFields": common.INPUT_FIELDS,
            "inputMechanismAndAll435ArraysFrozenAsOneState": True, "partOverrides": [],
            "codeHashes": {"web/src/scene.ts": native_sha},
            "actuallyExecutedImmutableNativeSourceSnapshots": [{
                "relativePath": "web/src/scene.ts", "snapshotPath": str(native_path),
                "sha256": native_sha,
            }],
            "geometry": None, "census": None,
        }
        detached_before = dict(copy.deepcopy(self.ray), id="detached-before", matrices=None)
        detached_after = dict(copy.deepcopy(self.ray), id="detached-after", partOverrides=[])
        rays = [detached_before, self.ray, detached_after]
        corruptions = [
            ("codeHashes", None), ("codeHashes", []),
            ("actuallyExecutedImmutableNativeSourceSnapshots", None),
            ("actuallyExecutedImmutableNativeSourceSnapshots", [None]),
            ("input", None), ("geometry", None), ("census", None),
        ]
        for field, malformed in corruptions:
            with self.subTest(field=field, malformed=malformed):
                export = dict(copy.deepcopy(header), **{field: malformed})
                returncode, result = self.run_cli(rays, json.dumps(export))
                self.assert_no_native_claim(returncode, result)
                self.assertIsNone(result["nativeExportSha256"])
                self.assertIsNone(result["unobservedInputFields"])
                self.assertEqual([row["status"] for row in result["rays"]],
                                 ["refused", "error", "refused"])
                self.assertEqual([row["request"] for row in result["rays"]], rays)
                self.assertEqual([row["id"] for row in result["rays"]],
                                 [ray["id"] for ray in rays])
                for row in result["rays"]:
                    self.assertIsInstance(row["reason"], str)
                    self.assertIsNone(row["guardValue"])
                    self.assertIsNone(row["hit"])


if __name__ == "__main__":
    unittest.main()
