"""Consumer-visible source identity and presentation refusal boundaries."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_script('compact-source-common.py', 'source_generation_common')
spin = load_script('compact-spin.py', 'source_generation_spin')


def exact_exposure():
    selected = {
        'shotId': 'machine', 'classification': 'machine', 'timeSeconds': 1,
        'decodedTimeSeconds': 1.0, 'decodedFrameIndex': 30,
        'sourceImage': {'frameIndex': 30, 'sourceSha256': 'a' * 64,
                        'pixelFormat': 'gray8', 'sha256Gray8': 'b' * 64,
                        'width': 1920, 'height': 1080},
        'landmarks': [],
    }
    donor = copy.deepcopy(selected)
    donor['timeSeconds'] = 1.001
    donor['landmarks'] = [{'anchorId': 'support', 'status': 'observed',
                          'pixel': [120.5, 340.25], 'role': 'check'}]
    return {
        'source': {'sha256': 'a' * 64, 'width': 1920, 'height': 1080},
        'shots': [{'id': 'machine', 'hasCorrespondingMachine': True}],
        'frames': [selected, donor],
    }


def retain(data, selected=None):
    if selected is None:
        selected = copy.deepcopy(data['frames'][0])
    return common.retain_exact_exposure_landmarks([selected], data)[0]


class ExactExposureLandmarkTests(unittest.TestCase):
    def test_gray8_preserves_original_observed_check(self):
        data = exact_exposure()
        originals = copy.deepcopy(data['frames'])
        result = retain(data)
        self.assertEqual(result['landmarks'], originals[1]['landmarks'])
        self.assertEqual(data['frames'], originals)

    def test_different_hash_pts_or_layout_cannot_supply_check(self):
        for mismatch in ('hash', 'pts', 'layout'):
            with self.subTest(mismatch=mismatch):
                data = exact_exposure()
                donor = data['frames'][1]
                if mismatch == 'hash':
                    donor['sourceImage']['sha256Gray8'] = 'c' * 64
                elif mismatch == 'pts':
                    donor['decodedTimeSeconds'] = 1.00001
                else:
                    donor['views'] = [{'id': 'main', 'rectSourcePixels': [0, 0, 960, 1080]}]
                self.assertEqual(retain(data)['landmarks'], [])

    def test_opposite_format_with_equal_hash_cannot_supply_check(self):
        data = exact_exposure()
        donor_image = data['frames'][1]['sourceImage']
        donor_image['pixelFormat'] = 'bgr8'
        donor_image['sha256Bgr8'] = donor_image['sha256Gray8']
        self.assertEqual(retain(data)['landmarks'], [])

    def test_contradictory_same_view_anchor_rejects(self):
        data = exact_exposure()
        data['frames'][0]['landmarks'] = copy.deepcopy(data['frames'][1]['landmarks'])
        # Explicit main and legacy unscoped main refer to the same source view.
        data['frames'][1]['landmarks'][0].update(viewId='main', pixel=[121, 340])
        with self.assertRaises(ValueError):
            retain(data)

    def test_ambiguous_selected_declaration_diagnosed_once(self):
        for use_original_object in (True, False):
            with self.subTest(use_original_object=use_original_object):
                data = exact_exposure()
                ambiguous = {'anchorId': 'ambiguous', 'viewId': 'missing',
                             'status': 'observed', 'pixel': [10, 20], 'role': 'check'}
                data['frames'][0]['landmarks'] = [ambiguous]
                selected = data['frames'][0] if use_original_object else copy.deepcopy(data['frames'][0])
                result = retain(data, selected)
                diagnostics = data['samplingDiagnostics']['exactExposureAliasLandmarks']
                ambiguity = [row for row in diagnostics['unavailable']
                             if row.get('anchorId') == 'ambiguous']
                self.assertEqual(len(ambiguity), 1)
                self.assertEqual(result['landmarks'], [ambiguous, *data['frames'][1]['landmarks']])


class SpinPresentationTests(unittest.TestCase):
    def assert_seed_refused_before_observations(self, seed):
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            (web / 'content').mkdir()
            (web / 'content' / 'XPQwKRt4Y2k.source-seeds.json').write_text(
                json.dumps({'views': {'endcard-analysis': seed}}))
            with patch.object(spin.common, 'WEB', web), patch.object(
                    spin.common, 'load_observations',
                    side_effect=AssertionError('Invalid seed reached source observation loading')):
                with self.assertRaises(ValueError):
                    spin.main()

    def test_invalid_presentation_refused_before_observation_load(self):
        self.assert_seed_refused_before_observations(
            {'presentation': 'mirror', 'presentationEvidence': 'A documented assumption.'})

    def test_override_requires_nonempty_string_evidence_before_observation_load(self):
        for evidence in (None, '', ' \n\t', 7):
            with self.subTest(evidence=evidence):
                seed = {'presentation': 'horizontal-mirror'}
                if evidence is not None:
                    seed['presentationEvidence'] = evidence
                self.assert_seed_refused_before_observations(seed)


if __name__ == '__main__':
    unittest.main()
