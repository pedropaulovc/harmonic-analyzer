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
rocker = load_script('compact-operation-rocker.py', 'source_generation_rocker')


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


def rocker_exposure():
    data = exact_exposure()
    image = copy.deepcopy(data['frames'][0]['sourceImage'])
    frame = copy.deepcopy(data['frames'][0])
    frame.update(timeSeconds=1.01, nativeFrame=30)
    frame.pop('sourceImage')
    data['frames'] = [frame]
    data['source'].update(videoId='4mBuyixt22U', durationSeconds=3,
                          fps={'numerator': 30, 'denominator': 1})
    data['shots'] = [{'id': 'machine', 'classification': 'machine',
                     'startSeconds': 0, 'endSeconds': 3,
                     'hasCorrespondingMachine': True}]
    data.update(model={}, anchors=[])
    state = {
        'nativeFrame': 30, 'timeSeconds': 1.01, 'sourceImage': image,
        'completeInput': {
            'crankTurns': 0, 'amplitudes': [0] * 20, 'phases': [0] * 20,
            'gearing': 'medium-medium', 'magnification': 1,
            'setup': {key: 0 for key in common.SETUP_FIELDS},
        },
    }
    seeds = {
        'states': [state],
        'bodyCandidate': {'camera': {'positionMetres': [0, 0, 1],
                                    'quaternion': [0, 0, 0, 1],
                                    'verticalFovDegrees': 45}},
    }
    return data, seeds


class RockerSourceImageTests(unittest.TestCase):
    def generate(self, data, seeds):
        with patch.object(rocker.common, 'load_observations',
                          return_value=copy.deepcopy(data)), patch.object(
                rocker, 'load_seeds', return_value=(copy.deepcopy(seeds), {})), patch.object(
                rocker, 'retain_generator_inputs'):
            return rocker.rocker()

    def test_exact_seed_image_follows_retained_exposure_not_playback_label(self):
        data, seeds = rocker_exposure()
        track = self.generate(data, seeds)
        alias = next(frame for frame in track['frames'] if frame['timeSeconds'] == 1)
        original = next(frame for frame in track['frames'] if frame['timeSeconds'] == 1.01)
        self.assertEqual(alias['retainedObservationTimeSeconds'], 1.01)
        for frame in (alias, original):
            self.assertEqual(frame['decodedTimeSeconds'], 1.0)
            self.assertEqual(frame['sourceImage'], seeds['states'][0]['sourceImage'])
            self.assertEqual(frame['views'][0]['input'], seeds['states'][0]['completeInput'])

    def test_nearest_input_uses_retained_time_without_borrowing_source_image(self):
        data, seeds = rocker_exposure()
        data['frames'][0].update(timeSeconds=1.49, decodedTimeSeconds=1.2,
                                 decodedFrameIndex=36, nativeFrame=36)
        early = seeds['states'][0]
        early.update(nativeFrame=33, timeSeconds=1.1)
        early['sourceImage']['frameIndex'] = 33
        late = copy.deepcopy(early)
        late.update(nativeFrame=45, timeSeconds=1.5)
        late['sourceImage']['frameIndex'] = 45
        late['completeInput']['crankTurns'] = 0.75
        seeds['states'].append(late)
        track = self.generate(data, seeds)
        alias = next(frame for frame in track['frames'] if frame['timeSeconds'] == 1)
        self.assertEqual(alias['retainedObservationTimeSeconds'], 1.49)
        self.assertEqual(alias['decodedTimeSeconds'], 1.2)
        self.assertNotIn('sourceImage', alias)
        self.assertEqual(alias['views'][0]['input'], late['completeInput'])
        self.assertEqual(alias['views'][0]['provenance']['kind'], 'chosen-feasible')
        self.assertEqual(alias['views'][0]['provenance']['unobservedInputFields'],
                         common.INPUT_FIELDS)

    def test_conflicting_source_or_decoded_identity_cannot_supply_seed_image(self):
        for mismatch in ('seed-image-frame', 'seed-source', 'decoded-pts', 'decoded-frame'):
            with self.subTest(mismatch=mismatch):
                data, seeds = rocker_exposure()
                if mismatch == 'seed-image-frame':
                    seeds['states'][0]['sourceImage']['frameIndex'] = 31
                elif mismatch == 'seed-source':
                    seeds['states'][0]['sourceImage']['sourceSha256'] = 'c' * 64
                elif mismatch == 'decoded-pts':
                    data['frames'][0]['decodedTimeSeconds'] = 31 / 30
                else:
                    data['frames'][0]['decodedFrameIndex'] = 31
                track = self.generate(data, seeds)
                frame = next(frame for frame in track['frames'] if frame['timeSeconds'] == 1)
                self.assertNotIn('sourceImage', frame)
                self.assertEqual(frame['views'][0]['input'], seeds['states'][0]['completeInput'])

    def test_existing_source_image_is_preserved_for_exact_and_nearest_inputs(self):
        for exact in (True, False):
            with self.subTest(exact=exact):
                data, seeds = rocker_exposure()
                image = copy.deepcopy(seeds['states'][0]['sourceImage'])
                data['frames'][0]['sourceImage'] = image
                seeds['states'][0]['sourceImage']['sha256Gray8'] = 'c' * 64
                if not exact:
                    seeds['states'][0]['nativeFrame'] = 31
                    seeds['states'][0]['sourceImage']['frameIndex'] = 31
                track = self.generate(data, seeds)
                alias = next(frame for frame in track['frames'] if frame['timeSeconds'] == 1)
                self.assertEqual(alias['sourceImage'], image)
                self.assertEqual(alias['views'][0]['input'], seeds['states'][0]['completeInput'])

    def test_1016_nearest_state_is_not_required_exposure_identity(self):
        for required in (True, False):
            with self.subTest(required=required):
                data, seeds = rocker_exposure()
                classification = 'machine' if required else 'non-machine'
                data['source'].update(durationSeconds=1016.1,
                                      fps={'numerator': 24000, 'denominator': 1001})
                data['shots'][0].update(endSeconds=1016.1,
                                        classification=classification,
                                        hasCorrespondingMachine=required)
                data['frames'][0].update(timeSeconds=1016,
                                         decodedTimeSeconds=1016.0149999999999,
                                         decodedFrameIndex=24360, nativeFrame=24360,
                                         classification=classification)
                seeds['states'][0].update(nativeFrame=24352,
                                          timeSeconds=1015.6813333333332)
                seeds['states'][0]['sourceImage']['frameIndex'] = 24352
                track = self.generate(data, seeds)
                frame = next(frame for frame in track['frames'] if frame['timeSeconds'] == 1016)
                self.assertEqual(frame['decodedTimeSeconds'], 1016.0149999999999)
                self.assertNotIn('sourceImage', frame)
                if required:
                    self.assertEqual(frame['views'][0]['input'], seeds['states'][0]['completeInput'])
                    self.assertEqual(frame['views'][0]['provenance']['kind'], 'chosen-feasible')
                else:
                    self.assertEqual(frame['views'], [])


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
