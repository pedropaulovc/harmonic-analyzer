"""Deterministic report regressions without renderer or video access."""
import unittest
from pathlib import Path
from unittest.mock import patch

from harmonic_sync.fit.report import (
    _acceptance_error,
    _coverage_frames,
    _frame_distribution,
)


class FitReportTests(unittest.TestCase):
    def test_acceptance_rejects_legacy_mean_without_directed_metrics(self):
        self.assertIsNone(_acceptance_error({'chamferPx': 100., 'iou': .75}))

    def test_acceptance_requires_both_directions(self):
        for direction in ('sourceToRenderChamferPx', 'renderToSourceChamferPx'):
            with self.subTest(direction=direction):
                self.assertIsNone(_acceptance_error({
                    'chamferPx': 100., 'iou': .75, direction: 100.,
                }))

    def test_acceptance_returns_worst_direction_at_iou_boundary(self):
        self.assertEqual(_acceptance_error({
            'chamferPx': 580., 'iou': .5,
            'sourceToRenderChamferPx': 200.,
            'renderToSourceChamferPx': 960.,
        }), 960.)

    def test_distribution_does_not_hide_over_threshold_direction_in_mean(self):
        for direction in ('sourceToRenderChamferPx', 'renderToSourceChamferPx'):
            with self.subTest(direction=direction):
                frame = {
                    'chamferPx': 500., 'iou': .75,
                    'sourceToRenderChamferPx': 39.,
                    'renderToSourceChamferPx': 39.,
                    direction: 961.,
                }
                self.assertEqual(_acceptance_error(frame), 961.)
                distribution = _frame_distribution([frame])
                self.assertEqual(distribution['medianPx'], 500.)
                self.assertEqual(distribution['framesAtOrBelow960Px'], 0)
                self.assertEqual(distribution['fractionAtOrBelow960Px'], 0.)
                self.assertEqual(distribution['rawFramesAtOrBelow960Px'], 1)
                self.assertEqual(distribution['rawPercentAtOrBelow960Px'], 100.)
                self.assertEqual(distribution['status'], 'fail')

    def test_raw_distribution_retains_low_iou_and_unsupported_denominator(self):
        frames = [
            {'chamferPx': 100., 'iou': .5,
             'sourceToRenderChamferPx': 80., 'renderToSourceChamferPx': 120.},
            {'chamferPx': 900., 'iou': .49,
             'sourceToRenderChamferPx': 900., 'renderToSourceChamferPx': 900.},
            {'chamferPx': None, 'iou': None},
        ]
        self.assertIsNone(_acceptance_error(frames[1]))
        distribution = _frame_distribution(frames)
        self.assertEqual(distribution['sampledFrames'], 3)
        self.assertEqual(distribution['finiteMetricFrames'], 2)
        self.assertEqual(distribution['validatedFrames'], 1)
        self.assertEqual(distribution['unvalidatedFrames'], 2)
        self.assertEqual(distribution['framesAtOrBelow960Px'], 1)
        self.assertAlmostEqual(distribution['fractionAtOrBelow960Px'], 1 / 3)
        self.assertEqual(distribution['rawFramesAtOrBelow960Px'], 2)
        self.assertAlmostEqual(distribution['rawPercentAtOrBelow960Px'], 200 / 3)
        self.assertEqual(distribution['medianPx'], 500.)
        self.assertAlmostEqual(distribution['p90Px'], 820.)
        self.assertEqual(distribution['maxPx'], 900.)

    def test_coverage_includes_transition_and_unsupported_source_samples(self):
        census = {
            'fps': [30, 1],
            'shots': [
                {'id': 'machine', 'classification': 'machine',
                 'startFrame': 0, 'endFrame': 2,
                 'views': [{'viewId': 'driver', 'role': 'driver'}]},
                {'id': 'transition', 'classification': 'transition',
                 'startFrame': 2, 'endFrame': 8,
                 'views': [{'viewId': 'driver', 'role': 'driver'}]},
                {'id': 'other', 'classification': 'non-machine',
                 'startFrame': 8, 'endFrame': 10,
                 'views': [{'viewId': 'driver', 'role': 'driver'}]},
            ],
        }
        source_indices = {
            'machine': {'frames': [{'index': 0}]},
            'transition': {'frames': [{'index': 2}, {'index': 4}, {'index': 6}]},
            'other': {'frames': [{'index': 8}]},
        }
        supported = {
            'viewId': 'driver', 'chamferPx': 100., 'iou': .75,
            'sourceToRenderChamferPx': 80., 'renderToSourceChamferPx': 120.,
        }
        residuals = {
            'shots': [{'id': shot['id']} for shot in census['shots']],
            'frames': [
                {**supported, 'shotId': 'machine', 'index': 0},
                {**supported, 'shotId': 'transition', 'index': 2},
                {'shotId': 'transition', 'viewId': 'driver', 'index': 6,
                 'chamferPx': None, 'iou': None},
                {**supported, 'shotId': 'other', 'index': 8},
            ],
        }

        def read_json(path):
            if path.name == 'shots.json':
                return census
            return source_indices[path.parent.parent.name]

        with patch('harmonic_sync.fit.report._read_json', side_effect=read_json):
            frames, coverage, _ = _coverage_frames(
                'synthetic', Path('/synthetic-source'), residuals,
            )

        by_key = {(row['shotId'], row['viewId'], row['index']): row for row in frames}
        self.assertEqual(set(by_key), {
            ('machine', 'driver', 0),
            ('transition', 'driver', 2),
            ('transition', 'driver', 4),
            ('transition', 'driver', 6),
        })
        self.assertEqual(by_key[('transition', 'driver', 2)]['chamferPx'], 100.)
        self.assertIsNone(by_key[('transition', 'driver', 4)]['chamferPx'])
        self.assertIsNone(by_key[('transition', 'driver', 6)]['chamferPx'])
        self.assertEqual(coverage['expectedViews'], [
            {'shotId': 'machine', 'viewId': 'driver'},
            {'shotId': 'transition', 'viewId': 'driver'},
        ])
        self.assertEqual(coverage['processedViews'], 2)
        self.assertEqual(coverage['qualifiedViews'], 1)
        self.assertEqual(coverage['missingViews'], [
            {'shotId': 'transition', 'viewId': 'driver',
             'sampledFrames': 3, 'unvalidatedFrames': 2},
        ])
        self.assertEqual(coverage['unknownSampleCountViews'], [])
        distribution = _frame_distribution(frames)
        self.assertEqual(distribution['sampledFrames'], 4)
        self.assertEqual(distribution['framesAtOrBelow960Px'], 2)
        self.assertEqual(distribution['unvalidatedFrames'], 2)
        self.assertEqual(distribution['fractionAtOrBelow960Px'], .5)


if __name__ == '__main__':
    unittest.main()
