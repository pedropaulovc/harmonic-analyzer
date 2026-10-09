"""Array-only fit support regressions; no native renderer is exercised."""
import math
import unittest
import warnings

import numpy as np

from harmonic_sync.fit.camera import CameraFitter, scale_camera
from harmonic_sync.fit.crank import (
    _edge_score,
    crank_support,
    decimate_crank,
    interpolate_turns,
    smooth_shot,
)
from harmonic_sync.fit.metrics import chamfer_metrics, mask_edges
from harmonic_sync.fit.setup import default_input, fit_setup


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

    def test_camera_prefers_matching_mask_over_tiny_render_on_dense_edges(self):
        sample = {**self.sample, 'edges': np.ones_like(self.sample['edges'])}
        tiny = np.zeros_like(self.ids)
        tiny[10:14, 14:18] = 1
        directed = chamfer_metrics(sample['edges'], mask_edges(tiny), source_width=32)
        self.assertEqual(directed['renderToSourceChamferPx'], 0.)
        for full_pose in (False, True):
            with self.subTest(full_pose=full_pose):
                score = CameraFitter(None, {}).loss_function(sample, full_pose=full_pose)
                matching_cost, tiny_cost = score(self.ids), score(tiny)
                self.assertTrue(math.isfinite(matching_cost))
                self.assertTrue(math.isfinite(tiny_cost))
                self.assertGreater(tiny_cost, matching_cost)

    def test_chamfer_reports_both_directions_and_untruncated_mean(self):
        source = np.zeros((4, 40), dtype=bool)
        source[2, :] = True
        render = np.zeros_like(source)
        render[2, :2] = True
        metrics = chamfer_metrics(source, render, source_width=400)
        self.assertEqual(metrics['renderToSourceChamferPx'], 0.)
        self.assertAlmostEqual(metrics['sourceToRenderChamferPx'], 185.25)
        self.assertAlmostEqual(metrics['chamferPx'], 92.625)
        reversed_metrics = chamfer_metrics(render, source, source_width=400)
        self.assertEqual(reversed_metrics['sourceToRenderChamferPx'], 0.)
        self.assertEqual(reversed_metrics['renderToSourceChamferPx'], metrics['sourceToRenderChamferPx'])
        self.assertEqual(reversed_metrics['chamferPx'], metrics['chamferPx'])

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

    def test_crank_scores_internal_group_motion_with_unchanged_union(self):
        aligned = self.ids.copy()
        aligned[6:18, 16:24] = 2
        shifted = self.ids.copy()
        shifted[6:18, 20:24] = 2
        self.assertTrue(np.array_equal(aligned > 0, shifted > 0))
        edges = np.zeros_like(self.sample['edges'])
        edges[5:7, 7:25] = edges[17:19, 7:25] = True
        edges[5:19, 7:9] = edges[5:19, 23:25] = True
        edges[5:19, 15:17] = True
        sample = {**self.sample, 'edges': edges}
        aligned_score = _edge_score(aligned, sample, [1, 2])
        shifted_score = _edge_score(shifted, sample, [1, 2])
        self.assertTrue(math.isfinite(aligned_score))
        self.assertTrue(math.isfinite(shifted_score))
        self.assertEqual(aligned_score, 0.)
        self.assertGreater(shifted_score, aligned_score)

    def test_crank_support_requires_visible_area_and_half_source_overlap(self):
        for visible, inside, eligible in ((149, 149, False), (150, 75, True),
                                          (150, 74, False), (0, 0, False)):
            with self.subTest(visible=visible, inside=inside):
                ids = np.full((270, 480), 2, dtype=np.uint16)
                ids[0, :visible] = 7
                mask = np.zeros(ids.shape, dtype=bool)
                mask[0, :inside] = True
                sample = {'width': 480, 'sourceWidth': 480, 'mask': mask, 'edges': mask.copy()}
                support = crank_support(ids, sample, {'crank': 7, 'static': 2})
                self.assertEqual(support['visiblePixels'], visible)
                self.assertEqual(support['minVisiblePixels'], 150)
                self.assertEqual(support['eligible'], eligible)
                self.assertEqual(support['sourceMaskFraction'], inside / visible if visible else 0.)

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

    def test_setup_locked_paths_keep_carried_values_without_rendering(self):
        carried = default_input('8KmVDxkia_w')
        carried['amplitudes'][0] = .625
        provenance = {'magnification': 'fitted', 'amplitudes.0': 'manual'}
        segment = {
            'id': 'locked', 'start': 0., 'end': 2.,
            'init': {'magnification': 2., 'amplitudes': [.25] + carried['amplitudes'][1:]},
            'fit': list(provenance), 'provenance': provenance,
        }
        result, evidence = fit_setup(
            None, segment, [{'input': carried, 'turns': .375, 't': 1.}], group_ids={},
        )
        self.assertEqual(result['input'], {k: v for k, v in carried.items() if k != 'crankTurns'})
        for path, source in provenance.items():
            self.assertEqual(result['provenance'][path], source)
            self.assertEqual(evidence['notIdentified'][path], f'{source}-authoritative')
        self.assertEqual(evidence['fixedCrankTurns'], .375)
        self.assertEqual(evidence['observable'], [])
        self.assertEqual(evidence['renders'], 0)

    def test_setup_manual_full_init_and_empty_request_keep_carried_input(self):
        carried = default_input('8KmVDxkia_w')
        carried['magnification'] = 3.
        carried['amplitudes'][0] = .625
        full_init = default_input('6dW6VYXp9HM')
        del full_init['crankTurns']
        segment = {'id': 'manual', 'start': 0., 'end': 2., 'init': full_init, 'fit': []}
        result, evidence = fit_setup(
            None, segment, [{'input': carried, 'turns': .375, 't': 1.}],
            group_ids={}, manual=True,
        )
        self.assertEqual(result['input'], {k: v for k, v in carried.items() if k != 'crankTurns'})
        self.assertEqual(set(result['provenance'].values()), {'manual'})
        self.assertEqual(evidence['status'], 'manual')
        self.assertEqual(evidence['requested'], [])
        self.assertEqual(evidence['observable'], [])
        self.assertEqual(evidence['renders'], 0)


if __name__ == '__main__':
    unittest.main()
