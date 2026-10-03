"""Native-support behavior at Intro's real camera-fit entry point.

Requires numpy, scipy, opencv-python-headless and the original raw2280 GLB:
  INTRO_RAW_NATIVE_MODEL_PATH=/private/raw/harmonic-analyzer.glb \
    python web/scripts/test_intro_feature_eligibility.py

History control: materialize f20571861:web/scripts/NAsM30MAHLg-calibrate-static.py
beside the current producer, then set INTRO_STATIC_PRODUCER_PATH to that absolute
file path. Do not undo a predicate by hand. The raw native support, camera samples
and test assertions stay identical; only the production module path changes.
A missing raw asset or mismatched identity fails the prerequisite, never a green skip.
"""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
