"""Array-only fit support regressions; no native renderer is exercised."""
import math
import unittest
import warnings

import numpy as np

from harmonic_sync.fit.camera import CameraFitter, scale_camera
from harmonic_sync.fit.crank import (
    _edge_score,
    decimate_crank,
    interpolate_turns,
    smooth_shot,
)


class NumericFitTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        self.addCleanup(self.warning_context.__exit__, None, None, None)
        warnings.simplefilter('error')
        mask = np.zeros((24, 32), dtype=bool)
        mask[6:18, 8:24] = True
        edges = np.zeros_like(mask)
        edges[6, 8:24] = edges[17, 8:24] = True
        edges[6:18, 8] = edges[6:18, 23] = True
        self.sample = {'mask': mask, 'edges': edges, 'width': 32, 'sourceWidth': 1920}
        self.ids = mask.astype(np.uint16)

    def test_camera_rejects_degenerate_arrays_with_finite_worst_cost(self):
        fitter = CameraFitter(None, {})
        cases = [
            (self.sample, np.zeros_like(self.ids)),
            (self.sample, np.ones_like(self.ids)),
            ({**self.sample, 'edges': np.zeros_like(self.sample['edges'])}, self.ids),
        ]
        for sample, ids in cases:
            with self.subTest(source_edges=sample['edges'].any(), area=np.count_nonzero(ids)):
                score = fitter.loss_function(sample)(ids)
                self.assertTrue(math.isfinite(score))
                self.assertEqual(score, 1e4)

    def test_camera_valid_array_has_finite_nonworst_cost(self):
        score = CameraFitter(None, {}).loss_function(self.sample)(self.ids)
        self.assertTrue(math.isfinite(score))
        self.assertLess(score, 1e4)

    def test_crank_missing_edges_and_filled_viewport_are_finite_worst_cost(self):
        cases = [
            ({**self.sample, 'edges': np.zeros_like(self.sample['edges'])}, self.ids),
            (self.sample, np.ones_like(self.ids)),
        ]
        for sample, ids in cases:
            with self.subTest(source_edges=sample['edges'].any(), area=np.count_nonzero(ids)):
                self.assertEqual(sample['mask'].dtype, np.dtype(bool))
                self.assertEqual(sample['edges'].dtype, np.dtype(bool))
                score = _edge_score(ids, sample, [1])
                self.assertTrue(math.isfinite(score))
                self.assertEqual(score, 1e4)

    def test_smoothing_preserves_exact_manual_anchors_including_reversal(self):
        keys = [
            {'t': float(j), 'turns': value, 'source': 'tracked'}
            for j, value in enumerate([0., .8, .2, 1.4, .6, -.2, .4])
        ]
        fixed = {1.: .375, 3.: 1.125, 5.: -.125, 7.: -.625}
        smoothed, _ = smooth_shot(keys, fixed)
        by_time = {key['t']: key for key in smoothed}
        for t, turns in fixed.items():
            with self.subTest(t=t):
                self.assertEqual(by_time[t]['turns'], turns)
                self.assertTrue(by_time[t]['manual'])

    def test_decimation_preserves_manual_times_provenance_and_error_bound(self):
        keys = [
            {'t': j / 100, 'turns': (j / 100) ** 2 + .03 * math.sin(j / 10),
             'source': 'tracked' if j < 35 or j >= 70 else 'inferred'}
            for j in range(101)
        ]
        fixed = {keys[17]['t'], keys[53]['t'], keys[89]['t']}
        reduced = decimate_crank(keys, tolerance=.005, fixed_times=fixed)
        retained = {key['t']: key for key in reduced}
        self.assertTrue(fixed <= retained.keys())
        for j in (0, 34, 35, 69, 70, 100):
            self.assertEqual(retained[keys[j]['t']], keys[j])
        self.assertLess(len(reduced), len(keys))
        for key in keys:
            self.assertLessEqual(abs(interpolate_turns(reduced, key['t']) - key['turns']), .005)

    def test_camera_principal_point_scales_in_inset_rect_local_coordinates(self):
        # A viewport at global (400, 200) still has a rect-local principal point.
        camera = {'principalPointViewportPixels': [75., 40.], 'verticalFovDegrees': 40.}
        scaled = scale_camera(camera, (300., 100.), (600., 300.))
        self.assertEqual(scaled['principalPointViewportPixels'], [150., 120.])
        self.assertEqual(camera['principalPointViewportPixels'], [75., 40.])
        self.assertEqual(scaled['verticalFovDegrees'], 40.)
        centered = scale_camera({}, (300., 100.), (600., 300.))
        self.assertEqual(centered['principalPointViewportPixels'], [300., 150.])


if __name__ == '__main__':
    unittest.main()
