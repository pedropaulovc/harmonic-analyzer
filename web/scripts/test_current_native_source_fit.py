"""Root-run adapter contract tests, not native-world/source qualification.

The eight-point arithmetic fixture has independent pinhole pixels. It is not a
fabricated real CURRENT462 pose or source observation. Real original CPU/raw
world exports must additionally be exercised by the parent CLI smoke.

python web/scripts/test_current_native_source_fit.py
"""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("current_native_source_fit_under_test", HERE / "current-native-source-fit.py")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
CLOSURE = "c" * 64


def fixture():
    # Independent CV pinhole camera, not fitter.project or fitted/GPU markers.
    coordinates = [(-0.15, -0.12, 1.8), (0.15, -0.12, 2.0), (-0.13, 0.12, 2.1),
                   (0.16, 0.11, 1.9), (-0.04, 0.01, 2.3), (0.07, -0.03, 1.7),
                   (-0.09, 0.07, 2.2), (0.08, 0.08, 1.85)]
    landmarks, rows = [], []
    for i, point in enumerate(coordinates):
        x, y, z = point
        landmark = {"anchorId": f"independent-test-point-{i}", "role": "fit" if i < 6 else "check",
                    "pixel": [960 + 1400 * x / z, 540 + 1400 * y / z], "status": "observed",
                    "method": "independent-pinhole-arithmetic-test-only", "uncertaintyPx": 1}
        landmarks.append(landmark)
        rows.append({"originalLandmark": copy.deepcopy(landmark), "status": "world-exported", "worldMetres": list(point)})
    image = {"frameIndex": 1, "pixelFormat": "bgr8", "width": 1920, "height": 1080,
             "sourceSha256": "a" * 64, "sha256Bgr8": "b" * 64}
    source = {"videoId": "eight-point-arithmetic-test-only", "sha256": "a" * 64, "width": 1920, "height": 1080}
    frame = {"sourceImage": image, "timeSeconds": 1, "decodedTimeSeconds": 1, "shotId": "fixture-only", "landmarks": landmarks}
    input_value = {"crankTurns": 0, "amplitudes": [0] * 20, "phases": [0] * 20, "gearing": "medium-medium", "magnification": 1,
                   "setup": {"counterHeightM": None, "meanLineAngleRad": 0, "platenOffsetM": 0, "wireFixtureOffsetM": 0,
                             "coneSwingRad": 0, "pinionCamRad": 0, "heldChannelTurns": 0, "driveCrankOffsetTurns": 0}}
    authored_frame = copy.deepcopy(frame)
    authored_frame["input"] = input_value
    return {"schemaVersion": 1, "kind": "current-native-source-camera-fit-packet",
            "model": {"rawSHA256": ADAPTER.RAW_SHA256, "deliverySHA256": ADAPTER.DELIVERY_SHA256, "originalCPUClosureSHA256": CLOSURE},
            "provenance": {k: "d" * 64 for k in ("originalObservationsSHA256", "authoredFrameSHA256", "selectionSHA256", "decodedFrameSHA256")},
            "original": {"source": source, "frame": frame}, "sourceBinding": {"sourceImage": copy.deepcopy(image), "sourceSha256": source["sha256"],
                "videoId": source["videoId"], "frameIndex": 1, "timeSeconds": 1, "decodedTimeSeconds": 1,
                "recordedOriginalDecodedTimeSeconds": 1, "shotId": "fixture-only", "originalViewId": "main",
                "decodedTimestampTicks": 30000, "timeBase": "1/30000"},
            "authored": {"frame": authored_frame, "input": input_value, "partOverrides": [],
                "inputSelection": {"field": "input", "state": "chosen-unmeasured", "evidence": "Independent test-only fixed pose; not source recovery", "ambiguities": ["test fixture only"]}},
            "rows": rows, "eligibility": {"ready": True}, "cameraInput": {"cameraFit": {}},
            "limitations": ["Test-only arithmetic fixture; no real source/native/GPU qualification"]}


class CurrentNativeFitTests(unittest.TestCase):
    def test_independent_nonplanar_fit_and_held_out_projection(self):
        packet = fixture()
        result = ADAPTER.fit_current_native_packet(packet, CLOSURE)
        self.assertEqual(result["status"], "candidate-passed")
        camera = result["camera"]
        self.assertLess(camera["fitMaxPx"], 1e-5)
        self.assertLess(camera["heldOutMaxPx"], 1e-5)
        self.assertAlmostEqual(camera["verticalFovDegrees"], math.degrees(2 * math.atan(1080 / 2800)), places=5)
        self.assertEqual(camera["thresholdPx"], 38.4)
        self.assertEqual([c["anchorId"] for c in camera["checkErrors"]], ["independent-test-point-6", "independent-test-point-7"])
        self.assertFalse(result["sourceAcceptance"])
        self.assertFalse(result["gpuAcceptance"])

    def test_check_failure_cannot_select_or_rescue_another_camera(self):
        good = fixture()
        baseline = ADAPTER.fit_current_native_packet(good, CLOSURE)
        bad = fixture()
        # Change an independent source CHECK fixture, not FIT pixels or worlds.
        # Matching original/row facts avoids testing a mere identity mismatch.
        for location in (bad["original"]["frame"]["landmarks"], bad["authored"]["frame"]["landmarks"]):
            location[6]["pixel"][0] += 90
        bad["rows"][6]["originalLandmark"]["pixel"][0] += 90
        failed = ADAPTER.fit_current_native_packet(bad, CLOSURE)
        self.assertEqual(failed["status"], "candidate-failed")
        self.assertGreater(failed["camera"]["heldOutMaxPx"], 89)
        for key in ("positionMetres", "quaternion", "verticalFovDegrees"):
            np.testing.assert_allclose(failed["camera"][key], baseline["camera"][key], rtol=0, atol=1e-10)

    def test_four_intro_style_fits_do_not_reuse_them_as_checks(self):
        packet = fixture()
        for row in packet["rows"][4:]:
            row["status"] = "unmeasured-native"
            row["reason"] = "Exact current raw/source mapping absent"
        result = ADAPTER.fit_current_native_packet(packet, CLOSURE)
        self.assertEqual(result["status"], "refused")
        self.assertEqual((result["distinctFitCount"], result["distinctCheckCount"]), (4, 0))
        self.assertIn("4/0", result["reasons"][0])
        self.assertEqual(len(result["unavailable"]), 4)
        self.assertIsNone(result["camera"])

    def test_duplicate_apex_or_fit_check_support_cannot_pass_by_named_row_count(self):
        for source_index, target_index in ((0, 1), (0, 6)):
            packet = fixture()
            packet["rows"][target_index]["worldMetres"] = packet["rows"][source_index]["worldMetres"].copy()
            with self.assertRaisesRegex(ValueError, "Coincident physical point"):
                ADAPTER.fit_current_native_packet(packet, CLOSURE)

    def test_original_roles_uncertainties_and_unavailable_rows_cannot_be_rewritten(self):
        for change in (lambda p: p["rows"][0]["originalLandmark"].update(role="check"),
                       lambda p: p["rows"][0]["originalLandmark"].update(uncertaintyPx=0),
                       lambda p: p["rows"].pop()):
            packet = fixture(); change(packet)
            with self.assertRaisesRegex(ValueError, "original role|omitted or duplicated"):
                ADAPTER.fit_current_native_packet(packet, CLOSURE)

    def test_nondefault_intrinsics_and_warp_do_not_become_pixel_fitting_fallbacks(self):
        packet = fixture(); packet["cameraInput"]["cameraFit"] = {"verticalFovDegrees": 40}
        with self.assertRaisesRegex(ValueError, "independent source evidence"):
            ADAPTER.fit_current_native_packet(packet, CLOSURE)
        warped = fixture(); warped["original"]["frame"]["imagePlaneWarp"] = {"kind": "original-separate-corner-obligation"}
        result = ADAPTER.fit_current_native_packet(warped, CLOSURE)
        self.assertEqual(result["status"], "refused")
        self.assertIn("corner/interior CHECK", result["reasons"][0])
        self.assertIsNone(result["camera"])

    def test_pinned_closure_and_chosen_input_cannot_self_authorize(self):
        with self.assertRaisesRegex(ValueError, "independently pinned"):
            ADAPTER.fit_current_native_packet(fixture(), "e" * 64)
        packet = fixture()
        packet["authored"]["frame"]["chosenInput"] = packet["authored"]["input"]
        packet["authored"]["inputSelection"].update(field="chosenInput", state="independently-measured")
        with self.assertRaisesRegex(ValueError, "cannot become independent source truth"):
            ADAPTER.fit_current_native_packet(packet, CLOSURE)


if __name__ == "__main__":
    unittest.main()
