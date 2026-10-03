"""Native-support camera fitting and frozen-state ray refusal at real entry points.

Requires numpy, scipy, opencv-python-headless and the original raw2280 GLB:
  INTRO_RAW_NATIVE_MODEL_PATH=/private/raw/harmonic-analyzer.glb \
    python web/scripts/test_intro_feature_eligibility.py

History controls select exact materialized git revisions, never edited predicates.
INTRO_STATIC_PRODUCER_PATH selects the static camera producer (f20571861).
INTRO_NATIVE_FEATURE_PRODUCER_PATH selects native eligibility, including exact
460b1a4 history controls for posed-array / proper-camera rejection assertions.
Missing or mismatched raw bytes fail, never a green skip. Admissibility fixtures
declare their own three-primitive test inventory, never a fabricated full435.
They retain the original raw marker and camera controls, but do not establish a
complete native solve, current462 geometry, source association or GPU acceptance.
Actual complete first-surface proof still requires a separately sealed export.
"""
import copy
import hashlib
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

    def run_cli(self, rays, export_content=None, request_content=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_path, output_path = root / "rays.json", root / "result.json"
            export_path = root / "missing-native-export.json"
            if export_content is not None:
                export_path.write_text(export_content)
            request_path.write_text(
                json.dumps({"rays": rays}) if request_content is None else request_content,
                encoding="utf-8",
            )
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

    def test_malformed_camera_shapes_are_refused_before_native_geometry(self):
        detached = dict(copy.deepcopy(self.ray), id="detached-marker", matrices=None)
        malformed_cameras = [
            ("origin", None), ("origin", [0., 0.]), ("origin", [[0.], [0.], [1.]]),
            ("origin", [False, 0., 1.]), ("origin", ["0", 0., 1.]),
            ("rotation", [0., 0., 1.]), ("rotation", None),
            ("rotation", [[1., 0., 0.], [0., 1.]]),
        ]
        for field, value in malformed_cameras:
            with self.subTest(field=field, value=value):
                malformed = dict(copy.deepcopy(self.ray), id="malformed-camera", **{field: value})
                rays = [detached, malformed]
                returncode, result = self.run_cli(rays)
                self.assert_no_native_claim(returncode, result)
                self.assertIsNone(result["nativeExportSha256"])
                self.assertIsNone(result["unobservedInputFields"])
                self.assertEqual([row["status"] for row in result["rays"]], ["refused", "refused"])
                self.assertEqual([row["request"] for row in result["rays"]], rays)
                self.assertEqual([row["id"] for row in result["rays"]], [ray["id"] for ray in rays])
                for row in result["rays"]:
                    self.assertIsInstance(row["reason"], str)
                    self.assertIsNone(row["guardValue"])
                    self.assertIsNone(row["hit"])

    def test_nonfinite_camera_retains_exact_raw_packet_identity(self):
        before = dict(copy.deepcopy(self.ray), id="detached-before", matrices={})
        after = dict(copy.deepcopy(self.ray), id="detached-after", partOverrides=[])
        for token in ("1e400", "NaN", "-Infinity"):
            with self.subTest(token=token):
                raw_text = (' \r\n{"rays":[\r\n' + json.dumps(before) +
                            ',\r\n{"id":"nonfinite-camera","origin":[' + token +
                            ',0,1],"rotation":' + json.dumps(self.ray["rotation"]) +
                            '},\r\n' + json.dumps(after) + '\r\n]}\r\n')
                returncode, result = self.run_cli(None, request_content=raw_text)
                self.assert_no_native_claim(returncode, result)
                self.assertEqual(result["rawRayRequestText"], raw_text)
                self.assertEqual(result["rayRequestSha256"],
                                 hashlib.sha256(raw_text.encode("utf-8")).hexdigest())
                self.assertEqual([row["status"] for row in result["rays"]],
                                 ["refused", "refused", "refused"])
                self.assertEqual(result["rays"][0]["request"], before)
                self.assertEqual(result["rays"][2]["request"], after)
                row = result["rays"][1]
                self.assertEqual(row["id"], "nonfinite-camera")
                self.assertIsNone(row["request"])
                self.assertEqual(row["requestRepresentation"], "raw-packet-entry")
                self.assertEqual(row["requestIndex"], 1)
                for row in result["rays"]:
                    self.assertIsInstance(row["reason"], str)
                    self.assertIsNone(row["guardValue"])
                    self.assertIsNone(row["hit"])


class PosedNativeAdmissibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SealedNativeRayRequestTests.setUpClass.__func__(cls)
        cls.profile = copy.deepcopy(cls.profile)
        cls.profile['finiteNib'].update(requiredNativeDrawableCount=3, requiredSpringDrawableCount=0)
        cls.profile['fixtureQualification'] = 'THREE_PRIMITIVE_ADMISSIBILITY_ONLY_NOT_NATIVE_SOLVE'
        cls.local, cls.faces = cls.feature.stored_primitive(
            cls.raw_path, cls.marker_path, cls.profile['finiteNib']['primitiveIndex'], cls.profile['modelSha256'])
        # Original actual marker matrix and camera control, kept independently
        # of the production validator. Other primitives are bounded triangles.
        cls.matrix = np.array([
            -1.2683255031580161e-7, -1.0000001000062668, 2.0317130798349802e-8, 0.,
            .70710678243166, -1.1111807210867963e-7, -.7071068370779496, 0.,
            .7071067991398629, -5.8255212252507367e-8, .7071067203634824, 0.,
            -.010350000113248825, .36079823093539387, -.14364999532699585, 1.,
        ]).reshape(4, 4, order='F')
        cls.marker_positions = (cls.matrix @ np.c_[cls.local, np.ones(len(cls.local))].T).T[:, :3]
        cls.point = cls.marker_positions[cls.profile['finiteNib']['nativeVertexIndex']]
        track = json.loads((WEB / 'content' / 'NAsM30MAHLg.source-track.json').read_text())
        cls.chosen_input = next(view['input'] for frame in track['frames']
                                for view in frame['views'] if isinstance(view.get('input'), dict))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile_path = self.root / 'test-profile.json'
        self.profile_path.write_text(json.dumps(self.profile))
        rotation = np.asarray(self.ray['rotation'])
        centre = (self.point + np.asarray(self.ray['origin'])) / 2
        u, v = .02 * rotation[:, 0], .02 * rotation[:, 1]
        self.occluding_positions = np.array([centre - u - v, centre + u - v, centre + 2 * v])
        self.remote_positions = np.array([[2., 2., 2.], [2.001, 2., 2.], [2., 2.001, 2.]])
        test_path = HERE / 'test_intro_feature_eligibility.py'
        test_sha = self.feature.digest(test_path)
        snapshot = self.root / 'executed-test-fixture.py'
        snapshot.write_bytes(test_path.read_bytes())
        self.header = {
            'fixtureQualification': 'SEALED_TEST_ARRAYS_NOT_ACTUAL_NATIVE_EXECUTION',
            'modelSha256': self.profile['modelSha256'],
            'nativeDrawableDenominator': 3, 'springDrawableCount': 0,
            'input': self.chosen_input, 'unobservedInputFields': self.feature.common.INPUT_FIELDS,
            'inputMechanismAndAll435ArraysFrozenAsOneState': True, 'partOverrides': [],
            'codeHashes': {'web/scripts/test_intro_feature_eligibility.py': test_sha},
            'actuallyExecutedImmutableNativeSourceSnapshots': [{
                'relativePath': 'web/scripts/test_intro_feature_eligibility.py',
                'snapshotPath': str(snapshot), 'sha256': test_sha,
            }],
            'geometry': {}, 'census': [],
        }
        p_offset = f_offset = 0
        for path, positions, faces, matrix in [
                (self.marker_path, self.marker_positions, self.faces, self.matrix),
                ('fixture/occluder', self.occluding_positions, [[0, 1, 2]], np.eye(4)),
                ('fixture/separated', self.remote_positions, [[0, 1, 2]], np.eye(4))]:
            faces = np.asarray(faces, dtype='<u4')
            self.header['census'].append({
                'path': path, 'vertexCount': len(positions), 'indexCount': faces.size,
                'positionByteOffset': p_offset, 'indexByteOffset': f_offset,
                'matrixWorld': matrix.flatten(order='F').tolist(), 'visibleByNativeGraph': True,
            })
            p_offset += np.asarray(positions, dtype='<f8').nbytes
            f_offset += faces.nbytes
        self.positions = np.concatenate([self.marker_positions, self.occluding_positions, self.remote_positions]).astype('<f8')
        self.indices = np.concatenate([self.faces.reshape(-1), [0, 1, 2], [0, 1, 2]]).astype('<u4')

    def seal(self, positions=None, indices=None, header=None):
        export = copy.deepcopy(self.header if header is None else header)
        for name, value, dtype in [
                ('positions', self.positions if positions is None else positions, 'little-endian IEEE754 float64'),
                ('indices', self.indices if indices is None else indices, 'little-endian uint32')]:
            payload = value if isinstance(value, bytes) else value.tobytes()
            path = self.root / (name + '.bin')
            path.write_bytes(payload)
            export['geometry'][name] = {'path': str(path), 'sha256': self.feature.digest(path),
                                        'bytes': len(payload), 'dtype': dtype}
        path = self.root / 'export.json'
        path.write_text(json.dumps(export, allow_nan=False))
        return path

    def native(self, export):
        return self.feature.FrozenNativeFirstSurface(export, self.raw_path, self.profile, WEB.parent)

    def cli(self, export, rays):
        packet, output = self.root / 'rays.json', self.root / 'result.json'
        packet.write_text(json.dumps({'rays': rays}, allow_nan=False))
        if output.exists():
            output.unlink()
        completed = subprocess.run([
            sys.executable, str(self.producer_path), '--model', str(self.raw_path),
            '--profile', str(self.profile_path), '--native-export', str(export),
            '--code-root', str(WEB.parent), '--rays', str(packet), '--output', str(output),
        ], capture_output=True, text=True)
        self.assertTrue(output.is_file(), completed.stderr)
        return completed.returncode, json.loads(output.read_text())

    def assert_rejected_payload(self, export):
        with self.assertRaises(ValueError):
            self.native(export)
        before = dict(copy.deepcopy(self.ray), id='detached-before', matrices={})
        after = dict(copy.deepcopy(self.ray), id='detached-after', partOverrides=[])
        second = dict(copy.deepcopy(self.ray), id='valid-camera-after-native-error')
        rays = [before, self.ray, second, after]
        returncode, result = self.cli(export, rays)
        self.assertNotEqual(returncode, 0)
        self.assertEqual([row['status'] for row in result['rays']], ['refused', 'error', 'error', 'refused'])
        self.assertEqual([row['request'] for row in result['rays']], rays)
        self.assertEqual([row['id'] for row in result['rays']], [ray['id'] for ray in rays])
        self.assertIsNone(result['completeNativeDenominator'])
        self.assertIsNone(result['nativeChosenInput'])
        self.assertIsNone(result['nativeExportSha256'])
        self.assertFalse(result['GPUAcceptance'])
        self.assertFalse(result['sourceAcceptance'])
        for row in result['rays']:
            self.assertIsNone(row['hit'])
            self.assertIsNone(row['guardValue'])

    def test_sealed_valid_arrays_retain_positive_and_occluder_controls(self):
        for occluded in (False, True):
            with self.subTest(occluded=occluded):
                positions = self.positions.copy()
                if not occluded:
                    positions[len(self.local):len(self.local) + 3] = self.remote_positions
                export = self.seal(positions=positions)
                native = self.native(export)
                value, hit = native.nib_guard(self.ray['origin'], self.ray['rotation'])
                self.assertEqual(hit['actualFiniteNibIsExactNearestPositiveSurface'], not occluded)
                self.assertEqual(hit['partPath'], 'fixture/occluder' if occluded else self.marker_path)
                if occluded:
                    self.assertLess(value, 0)
                else:
                    self.assertGreater(value, 0)
                returncode, result = self.cli(export, [self.ray])
                self.assertEqual(returncode, 0)
                self.assertEqual(result['rays'][0]['status'], 'measured')
                self.assertEqual(result['rays'][0]['hit']['actualFiniteNibIsExactNearestPositiveSurface'], not occluded)

    def test_nonfinite_coordinates_reject_visible_and_hidden_whole_payload(self):
        for value in (np.nan, np.inf, -np.inf):
            for visible in (True, False):
                with self.subTest(value=value, visible=visible):
                    positions = self.positions.copy()
                    positions[len(self.local):len(self.local) + 3] = value
                    header = copy.deepcopy(self.header)
                    header['census'][1]['visibleByNativeGraph'] = visible
                    self.assert_rejected_payload(self.seal(positions=positions, header=header))

    def test_payload_byte_coverage_is_exact_not_hash_only(self):
        p, f = self.positions.tobytes(), self.indices.tobytes()
        for positions, indices in [(p[:-24], f), (p, f[:-12]), (p[:-1], f), (p, f[:-1]),
                                   (p + bytes(24), f), (p, f + bytes(12))]:
            with self.subTest(positionBytes=len(positions), indexBytes=len(indices)):
                self.assert_rejected_payload(self.seal(positions, indices))

    def test_declared_payload_dtype_and_size_match_actual_bytes(self):
        for name, field, value in [('positions', 'dtype', 'little-endian IEEE754 float32'),
                                   ('indices', 'dtype', 'little-endian uint16'),
                                   ('positions', 'bytes', self.positions.nbytes - 8),
                                   ('indices', 'bytes', self.indices.nbytes - 4)]:
            with self.subTest(name=name, field=field):
                export = self.seal()
                header = json.loads(export.read_text())
                header['geometry'][name][field] = value
                export.write_text(json.dumps(header))
                self.assert_rejected_payload(export)

    def test_indices_cannot_leave_their_own_primitive(self):
        for index in (3, np.iinfo(np.uint32).max):
            with self.subTest(index=index):
                indices = self.indices.copy()
                indices[self.faces.size] = index
                self.assert_rejected_payload(self.seal(indices=indices))

    def test_census_counts_offsets_and_triangle_coverage_are_bounded(self):
        for field, value in [('vertexCount', -1), ('vertexCount', 2**80), ('indexCount', 2),
                             ('positionByteOffset', 2**80), ('indexByteOffset', 2**80),
                             ('positionByteOffset', 0), ('indexByteOffset', 0),
                             ('positionByteOffset', self.header['census'][1]['positionByteOffset'] + 8)]:
            with self.subTest(field=field, value=value):
                header = copy.deepcopy(self.header)
                header['census'][1][field] = value
                self.assert_rejected_payload(self.seal(header=header))

    def test_nonrotation_cameras_are_refused_at_api_and_cli_preload_boundaries(self):
        export = self.seal()
        native = self.native(export)
        rotation = np.asarray(self.ray['rotation'])
        depth = float(-((self.point - np.asarray(self.ray['origin'])) @ rotation)[2])
        scaled = rotation.copy()
        scaled[:, 2] *= (.005 / .9) / depth
        reflection = rotation.copy()
        reflection[:, 0] *= -1
        for invalid in (scaled, np.zeros((3, 3)), reflection, np.diag([1., 1., 0.]), np.full((3, 3), 1e300)):
            with self.subTest(rotation=invalid.tolist()):
                with self.assertRaises(ValueError):
                    native.nib_guard(self.ray['origin'], invalid)
                ray = dict(copy.deepcopy(self.ray), id='invalid-camera', rotation=invalid.tolist())
                detached = dict(copy.deepcopy(self.ray), id='detached', matrices={})
                returncode, result = self.cli(self.root / 'missing.json', [detached, ray])
                self.assertNotEqual(returncode, 0)
                self.assertEqual([row['status'] for row in result['rays']], ['refused', 'refused'])
                self.assertEqual([row['request'] for row in result['rays']], [detached, ray])
                self.assertIsNone(result['nativeExportSha256'])
                self.assertIsNone(result['completeNativeDenominator'])
                rays = [detached, ray, self.ray]
                returncode, result = self.cli(export, rays)
                self.assertNotEqual(returncode, 0)
                self.assertEqual([row['status'] for row in result['rays']], ['refused', 'refused', 'measured'])
                self.assertEqual([row['request'] for row in result['rays']], rays)
                self.assertFalse(result['rays'][2]['hit']['actualFiniteNibIsExactNearestPositiveSurface'])

    def test_float32_camera_rotation_preserves_realizable_positive_control(self):
        positions = self.positions.copy()
        positions[len(self.local):len(self.local) + 3] = self.remote_positions
        export = self.seal(positions=positions)
        rotation = np.asarray(self.ray['rotation'], dtype=np.float32)
        _, hit = self.native(export).nib_guard(self.ray['origin'], rotation)
        self.assertTrue(hit['actualFiniteNibIsExactNearestPositiveSurface'])
        ray = dict(copy.deepcopy(self.ray), rotation=rotation.tolist())
        returncode, result = self.cli(export, [ray])
        self.assertEqual(returncode, 0)
        self.assertTrue(result['rays'][0]['hit']['actualFiniteNibIsExactNearestPositiveSurface'])


if __name__ == "__main__":
    unittest.main()
