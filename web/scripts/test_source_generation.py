"""Consumer-visible source identity and presentation refusal boundaries."""
import copy
import importlib.util
import json
import os
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
camera_tracks = load_script(os.environ.get('SOURCE_GENERATOR_PATH',
                                          'generate-analysis-synthesis-source-tracks.py'),
                            'source_generation_camera_tracks')


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


class ChosenCameraNativeClockTests(unittest.TestCase):
    def fixture(self, track_schema):
        first, last = 623, 637
        rate = 24000 / 1001
        shot = {'id': 'presenter-to-spin', 'startSeconds': 25.984291667,
                'endSeconds': 26.609916667,
                ('nativeStartFrame' if track_schema else 'startDecodedFrameIndex'): first}
        rows = [{'shotId': shot['id'], 'decodedTimeSeconds': index / rate,
                 ('sourceFrameIndex' if track_schema else 'decodedFrameIndex'): index,
                 'camera': None, 'views': [{'id': 'main', 'camera': None,
                    'rectSourcePixels': [0, 0, 1920, 1080], 'presentation': 'native'}]}
                for index in range(first, last + 1)]
        data = {'source': {'sha256': 'a' * 64, 'width': 1920, 'height': 1080,
                          'fps': {'numerator': 24000, 'denominator': 1001}},
                'shots': [shot], 'frames': rows}
        permission = {'shotId': shot['id'], 'viewId': 'main', 'componentFamily': 'whole',
                      'cameraProvenanceKind': 'source-informed-framing',
                      'measurementStatus': 'unmeasured', 'cameraInterpolation': 'continuous-shot',
                      'cameraInterpolationEvidence': 'Chosen single-body continuous reframing.',
                      'cameraContinuityFamily': 'chosen:presenter-to-spin:main',
                      'startSeconds': shot['startSeconds'], 'endSeconds': shot['endSeconds'],
                      'startDecodedFrameIndex': first, 'lastDecodedFrameIndex': last}
        packet = {'schemaVersion': 1, 'videoId': '8KmVDxkia_w',
                  'sourceSha256': data['source']['sha256'], 'permissions': [permission]}
        return data, packet

    def load_permission(self, data, packet):
        generator = camera_tracks.Generator.__new__(camera_tracks.Generator)
        generator.data = data
        generator.shots = {shot['id']: shot for shot in data['shots']}
        return generator.chosen_camera_continuity_packet('8KmVDxkia_w', packet)

    def test_both_native_schemas_accept_decimal_cut_rounding_without_mutation(self):
        for track_schema in (False, True):
            with self.subTest(track_schema=track_schema):
                data, packet = self.fixture(track_schema)
                original = copy.deepcopy(data)
                permissions = self.load_permission(data, packet)
                self.assertEqual(permissions[('presenter-to-spin', 'main')], packet['permissions'][0])
                self.assertEqual(data, original)

    def test_missing_conflicting_or_off_clock_native_evidence_is_refused(self):
        for mismatch in ('missing-row', 'shot-index', 'row-index', 'nan-pts',
                         'off-clock', 'frame-camera', 'view-camera', 'layout', 'presentation'):
            with self.subTest(mismatch=mismatch):
                data, packet = self.fixture(True)
                row = data['frames'][0]
                if mismatch == 'missing-row':
                    data['frames'].pop(7)
                elif mismatch == 'shot-index':
                    data['shots'][0]['startDecodedFrameIndex'] = 624
                elif mismatch == 'row-index':
                    row['decodedFrameIndex'] = 624
                elif mismatch == 'nan-pts':
                    row['decodedTimeSeconds'] = float('nan')
                elif mismatch == 'off-clock':
                    data['frames'][7]['decodedTimeSeconds'] += 0.01
                elif mismatch == 'frame-camera':
                    row['camera'] = {'verticalFovDegrees': 30}
                elif mismatch == 'view-camera':
                    row['views'][0]['camera'] = {'verticalFovDegrees': 30}
                elif mismatch == 'presentation':
                    row['views'][0]['presentation'] = 'horizontal-mirror'
                else:
                    row['views'][0]['rectSourcePixels'] = [0, 0, 960, 1080]
                with self.assertRaises(ValueError):
                    self.load_permission(data, packet)


class PresenterOriginalViewTests(unittest.TestCase):
    def source(self, legacy_views=True):
        # Exercise the real retained producer input and constructor, including
        # the outgoing/incoming null-camera layout accepted before normalization.
        data = camera_tracks.common.load_observations('8KmVDxkia_w', prefer_track=True)
        if not legacy_views:
            return data
        for frame in data['frames']:
            if frame['shotId'] == 'presenter-to-spin':
                view = {'rectSourcePixels': [0, 0, data['source']['width'], data['source']['height']],
                        'presentation': 'native', 'camera': None}
                frame['views'] = [dict(view, id=name) for name in ('outgoing', 'incoming')]
        return data

    def construct(self, data):
        with patch.object(camera_tracks.common, 'load_observations', return_value=data):
            return camera_tracks.Generator('8KmVDxkia_w')

    def test_existing_retained_source_accepts_permission(self):
        generator = self.construct(self.source(legacy_views=False))
        self.assertIn(('presenter-to-spin', 'main'), generator.chosen_camera_permissions)

    def test_legacy_null_views_normalize_and_apply_permission_at_native_first_exposure(self):
        generator = self.construct(self.source())
        frame = next(frame for frame in generator.data['frames']
                     if frame['shotId'] == 'presenter-to-spin' and frame['sourceFrameIndex'] == 623)
        self.assertLess(frame['decodedTimeSeconds'], generator.shots[frame['shotId']]['startSeconds'])
        self.assertEqual([view['id'] for view in frame['views']], ['main'])
        track = {'frames': [{**frame, 'views': generator.views(frame)}]}
        generator.camera_metadata(track)
        permission = generator.chosen_camera_permissions[(frame['shotId'], 'main')]
        view = track['frames'][0]['views'][0]
        self.assertEqual(view['cameraInterpolation'], 'continuous-shot')
        self.assertEqual(view['cameraContinuityFamily'], permission['cameraContinuityFamily'])
        self.assertEqual(view['cameraProvenance']['kind'], 'source-informed-framing')

    def test_unsupported_original_views_are_refused_before_normalization(self):
        for mismatch in ('camera', 'rect', 'presentation', 'empty', 'missing', 'warp',
                         'resolved-warp', 'crossfade', 'unexpected-id', 'duplicate-id'):
            with self.subTest(mismatch=mismatch):
                data = self.source()
                frame = next(frame for frame in data['frames'] if frame['shotId'] == 'presenter-to-spin')
                view = frame['views'][1]
                if mismatch == 'camera':
                    view['camera'] = {'verticalFovDegrees': 30}
                elif mismatch == 'rect':
                    view['rectSourcePixels'] = [960, 0, 960, 1080]
                elif mismatch == 'presentation':
                    view['presentation'] = 'horizontal-mirror'
                elif mismatch == 'empty':
                    frame['views'] = []
                elif mismatch == 'missing':
                    frame.pop('views')
                elif mismatch in ('warp', 'resolved-warp'):
                    view['resolvedImagePlaneWarp' if mismatch == 'resolved-warp' else 'imagePlaneWarp'] = {
                        'kind': 'homography', 'unwarpedViewportPixels': [0, 0, 1920, 1080],
                        'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]}
                elif mismatch == 'crossfade':
                    view['composite'] = {'mode': 'crossfade', 'groupId': 'body',
                                         'imageLayerId': 'incoming', 'opacity': 0.5}
                elif mismatch == 'unexpected-id':
                    view['id'] = 'unmapped-body'
                else:
                    frame['views'].append(copy.deepcopy(view))
                original = copy.deepcopy(frame.get('views'))
                with self.assertRaises(ValueError):
                    self.construct(data)
                self.assertEqual(frame.get('views'), original)

    def test_unrelated_original_source_views_remain_outside_permission_guard(self):
        data = self.source()
        frame = next(frame for frame in data['frames']
                     if frame['shotId'] != 'presenter-to-spin' and frame.get('views'))
        frame['views'][0]['rectSourcePixels'] = [0, 0, 960, 1080]
        original = copy.deepcopy(frame['views'])
        generator = self.construct(data)
        self.assertEqual(frame['views'], original)
        self.assertIn(('presenter-to-spin', 'main'), generator.chosen_camera_permissions)

    def test_presenter_without_selected_permission_keeps_existing_normalization(self):
        data = self.source()
        frame = next(frame for frame in data['frames'] if frame['shotId'] == 'presenter-to-spin')
        frame['views'][1]['rectSourcePixels'] = [960, 0, 960, 1080]
        packet = {'schemaVersion': 1, 'videoId': '8KmVDxkia_w',
                  'sourceSha256': data['source']['sha256'], 'permissions': []}
        permission_path = camera_tracks.WEB / 'content/8KmVDxkia_w.chosen-camera-continuity.json'
        read_text = Path.read_text

        def read_packet(path, *args, **kwargs):
            return json.dumps(packet) if path == permission_path else read_text(path, *args, **kwargs)

        with patch.object(Path, 'read_text', read_packet):
            generator = self.construct(data)
        self.assertEqual(generator.chosen_camera_permissions, {})
        self.assertEqual([view['id'] for view in frame['views']], ['main'])


class AnalysisAutomaticMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = camera_tracks.Generator('6dW6VYXp9HM')
        cls.track = cls.generator.build()
        # Fixtures stay beside these tests even when the actual producer is an
        # earlier git revision selected by SOURCE_GENERATOR_PATH.
        content = HERE.parent / 'content'
        cls.packet = json.loads((content / '6dW6VYXp9HM.automatic-motion.json').read_text())
        cls.controls = json.loads((content / '6dW6VYXp9HM.motion-controls.json').read_text())
        cls.visible = json.loads((content / '6dW6VYXp9HM.visible-crank-motion.json').read_text())
        cls.gauge = json.loads((content / '6dW6VYXp9HM.visible-crank-gauge.json').read_text())

    def native_frame(self, index):
        return next(frame for frame in self.generator.data['frames']
                    if frame.get('decodedFrameIndex') == index
                    and abs(frame['timeSeconds'] - frame['decodedTimeSeconds']) < 1e-9)

    def test_all_204_exact_native_keys_use_cumulative_drive_and_fixed_complete_input(self):
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for authority in self.packet['frames']:
            with self.subTest(index=authority['frameIndex']):
                frame = generated[authority['timeSeconds']]
                original = self.native_frame(authority['frameIndex'])
                self.assertEqual(frame['decodedTimeSeconds'], original['decodedTimeSeconds'])
                self.assertEqual(frame['sourceImage'], authority['sourceImage'])
                self.assertEqual(frame['sourceImage'], original['sourceImage'])
                self.assertEqual(frame['shotId'], 'analysis-22')
                bank = next(view for view in frame['views'] if view['id'] == 'bar-bank')
                expected = copy.deepcopy(self.packet['fixedInput'])
                expected['crankTurns'] = authority['crankTurns']
                self.assertEqual(bank['input'], expected)
                original_view = next(view for view in original['views'] if view['id'] == 'bar-bank')
                self.assertEqual(bank['rectSourcePixels'], original_view['rectSourcePixels'])
                self.assertEqual(bank['presentation'], original_view['presentation'])
                self.assertEqual(bank['camera'],
                                 camera_tracks.common.compact_camera(self.generator.candidate['nativeCameraRecord']))
        self.assertEqual(generated[self.packet['frames'][0]['timeSeconds']]['views'][0]['input']['crankTurns'], 0)
        self.assertGreater(generated[self.packet['frames'][-1]['timeSeconds']]['views'][0]['input']['crankTurns'], 3)

    def test_exact_native_keys_preserve_all_raw_fit_check_pixels_and_nulls(self):
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        fields = ('anchorId', 'viewId', 'role', 'pixel', 'status', 'method',
                  'uncertaintyPx', 'trackingEvidence', 'measurementEvidence')
        for control in self.generator.bank_controls['frames']:
            with self.subTest(index=control['decodedFrameIndex']):
                frame = generated[control['timeSeconds']]
                points = {(point['viewId'], point['anchorId']): point for point in frame['landmarks']}
                for point in control['landmarks']:
                    expected = {key: copy.deepcopy(point[key]) for key in fields if key in point}
                    self.assertEqual(points[(point['viewId'], point['anchorId'])], expected)
                unavailable = {(point['viewId'], point['anchorId']): point
                               for point in frame.get('unavailable', []) if 'anchorId' in point}
                for point in control['unavailable']:
                    key = (point['viewId'], point['anchorId'])
                    self.assertNotIn(key, points)
                    self.assertEqual(unavailable[key]['reason'], point['reason'])
        anchors = {anchor['id']: anchor for anchor in self.track['anchors']}
        for anchor in self.generator.bank_controls['anchors']:
            self.assertEqual(anchors[anchor['id']]['partPath'], anchor['partPath'])
            self.assertEqual(anchors[anchor['id']]['partLocalMetres'], anchor['partLocalMetres'])

    def test_actual_source_seconds_interpolate_cumulative_drive_not_phase_or_label(self):
        left, right = self.packet['frames'][34:36]
        frame = copy.deepcopy(self.native_frame(left['frameIndex']))
        frame.pop('decodedFrameIndex')
        frame.pop('sourceImage')
        frame['decodedTimeSeconds'] = left['timeSeconds'] + 0.25 * (right['timeSeconds'] - left['timeSeconds'])
        frame['timeSeconds'] = 117
        view = frame['views'][0]
        value, _ = self.generator.input(frame, 'bar', view)
        self.assertAlmostEqual(value['crankTurns'],
                               left['crankTurns'] + 0.25 * (right['crankTurns'] - left['crankTurns']), places=12)
        for field in ('amplitudes', 'phases', 'gearing', 'magnification', 'setup'):
            self.assertEqual(value[field], self.packet['fixedInput'][field])

    def test_integer_alias_retains_actual_exposure_drive_and_source_identity(self):
        frame = next(frame for frame in self.track['frames'] if frame['timeSeconds'] == 117)
        authority = next(row for row in self.packet['frames'] if row['frameIndex'] == 3506)
        self.assertEqual(frame['sourceImage'], authority['sourceImage'])
        self.assertAlmostEqual(frame['decodedTimeSeconds'], authority['timeSeconds'], places=12)
        bank = next(view for view in frame['views'] if view['id'] == 'bar-bank')
        self.assertEqual(bank['input']['crankTurns'], authority['crankTurns'])
        self.assertNotEqual(bank['input']['crankTurns'],
                            next(row for row in self.packet['frames'] if row['frameIndex'] == 3507)['crankTurns'])

    def test_wrong_shot_view_family_or_presentation_keeps_original_inverse_input(self):
        for boundary in ('shot', 'view', 'family', 'presentation', 'before', 'shot-end'):
            with self.subTest(boundary=boundary):
                frame = copy.deepcopy(self.native_frame(3450))
                view, family = frame['views'][0], 'bar'
                if boundary == 'shot':
                    frame['shotId'] = 'analysis-23'
                elif boundary == 'view':
                    view['id'] = 'main'
                elif boundary == 'family':
                    view['id'] = 'pen-inset'
                elif boundary == 'presentation':
                    view['presentation'] = 'native'
                elif boundary == 'before':
                    frame['decodedTimeSeconds'] = self.packet['interval']['startSeconds'] - 0.01
                else:
                    frame['decodedTimeSeconds'] = self.generator.shots['analysis-22']['endSeconds']
                family = self.generator.family(frame, view)
                time = frame['decodedTimeSeconds']
                snapshots = self.generator.analysis_snapshots
                first = snapshots[0]['sourceFrameIdentity']['timeSeconds']
                last = snapshots[-1]['sourceFrameIdentity']['timeSeconds']
                if family == 'bar' and first <= time <= last:
                    expected = min(snapshots, key=lambda row: abs(row['sourceFrameIdentity']['timeSeconds'] - time))
                else:
                    expected = snapshots[0] if time < first else snapshots[-1]
                rendered = next(row for row in self.generator.views(frame) if row['id'] == view['id'])
                self.assertEqual(rendered['input'], expected['chosenInput'])

    def test_endpoint_held_for_every_remaining_same_shot_key_without_source_image(self):
        end = self.packet['interval']['endSeconds']
        expected = copy.deepcopy(self.packet['fixedInput'])
        expected['crankTurns'] = self.packet['frames'][-1]['crankTurns']
        held = [frame for frame in self.track['frames']
                if frame['shotId'] == 'analysis-22' and frame['decodedTimeSeconds'] > end]
        for frame in held:
            bank = next(view for view in frame['views'] if view['id'] == 'bar-bank')
            self.assertEqual(bank['input'], expected)
        for index in (3580, 3730):
            original = self.native_frame(index)
            self.assertIsNone(original.get('sourceImage'))
            bank = next(view for view in self.generator.views(original) if view['id'] == 'bar-bank')
            self.assertEqual(bank['input'], expected)
        self.assertAlmostEqual(held[-1]['decodedTimeSeconds'], 3730 / (30000 / 1001), places=9)
        next_shot = self.native_frame(3731)
        for view in self.generator.views(next_shot):
            self.assertEqual(view['input'], self.generator.analysis_snapshots[-1]['chosenInput'])
        diagnostics = self.track['cpuDiagnostics']['analysisAutomaticMotion']
        self.assertEqual(diagnostics['domain']['measurementStatus'], 'conditional-source-fit')
        self.assertEqual(diagnostics['domain']['endSeconds'], end)
        self.assertEqual(diagnostics['endpointHold']['kind'], 'chosen-endpoint-hold')
        self.assertEqual(diagnostics['endpointHold']['measurementStatus'], 'unmeasured')
        self.assertEqual(diagnostics['endpointHold']['endSeconds'], self.generator.shots['analysis-22']['endSeconds'])
        self.assertFalse(diagnostics['stageAcceptance'])
        self.assertEqual(diagnostics['physicalCrankDirection'], 'unobservable')
        self.assertEqual(diagnostics['absolutePhysicalCrankPhase'], 'unobservable')

    def test_changed_or_missing_pinned_artifact_rejects_instead_of_falling_back(self):
        for target in (camera_tracks.AUTOMATIC_MOTION, camera_tracks.MOTION_CONTROLS):
            for missing in (False, True):
                with self.subTest(target=target, missing=missing), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    for path in (camera_tracks.AUTOMATIC_MOTION, camera_tracks.MOTION_CONTROLS):
                        if path == target and missing:
                            continue
                        destination = root / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        data = (camera_tracks.ROOT / path).read_bytes()
                        destination.write_bytes(data + b' ' if path == target else data)
                    with patch.object(camera_tracks, 'ROOT', root), self.assertRaises(ValueError):
                        self.generator.analysis_automatic_motion_packet()

    def test_semantically_unsupported_native_authority_rejects(self):
        for mismatch in ('kind', 'source', 'model', 'fps', 'missing-frame', 'duplicate-frame',
                         'pts', 'nan-pts', 'image', 'source-image', 'native-math', 'camera',
                         'station', 'amplitudes', 'phases', 'setup', 'nonfinite-drive',
                         'backward-drive', 'physical-sign', 'stage-claim'):
            with self.subTest(mismatch=mismatch):
                packet, controls = copy.deepcopy(self.packet), copy.deepcopy(self.controls)
                generator = copy.copy(self.generator)
                if mismatch == 'kind':
                    packet['kind'] = 'chosen-generic-animation'
                elif mismatch == 'source':
                    packet['authority']['videoSha256'] = '0' * 64
                elif mismatch == 'model':
                    packet['authority']['nativeModelSha256'] = '0' * 64
                elif mismatch == 'fps':
                    generator.data = {**generator.data, 'source': {**generator.data['source'], 'fps': {'numerator': 30, 'denominator': 1}}}
                elif mismatch == 'missing-frame':
                    packet['frames'].pop(80)
                elif mismatch == 'duplicate-frame':
                    packet['frames'][80]['frameIndex'] = packet['frames'][79]['frameIndex']
                elif mismatch == 'pts':
                    packet['frames'][80]['timeSeconds'] += 0.001
                elif mismatch == 'nan-pts':
                    packet['frames'][80]['timeSeconds'] = float('nan')
                elif mismatch == 'image':
                    packet['frames'][80]['sourceImage']['sha256Bgr8'] = '0' * 64
                elif mismatch == 'source-image':
                    index = packet['frames'][80]['frameIndex']
                    generator.data = {**generator.data, 'frames': [
                        {**frame, 'sourceImage': None} if frame.get('decodedFrameIndex') == index else frame
                        for frame in generator.data['frames']]}
                elif mismatch == 'native-math':
                    packet['diagnostics']['nativeForwardSmoke']['nativeMathSha256']['web/src/mechanics.ts'] = '0' * 64
                elif mismatch == 'camera':
                    controls['frozenCandidate']['nativeCameraRecord']['verticalFovDegrees'] += 1
                elif mismatch == 'station':
                    packet['stationCorrespondence'][0]['nativeStationIndex'] = 0
                elif mismatch == 'amplitudes':
                    packet['fixedInput']['amplitudes'].pop()
                elif mismatch == 'phases':
                    packet['fixedInput']['phases'][0] = float('nan')
                elif mismatch == 'setup':
                    packet['fixedInput']['setup']['coneSwingRad'] = 0.1
                elif mismatch == 'nonfinite-drive':
                    packet['frames'][80]['crankTurns'] = float('inf')
                elif mismatch == 'backward-drive':
                    packet['frames'][80]['crankTurns'] = -1
                elif mismatch == 'physical-sign':
                    packet['authority']['physicalCrankDirection'] = 'measured-positive'
                else:
                    packet['integration']['stageAcceptance'] = True
                with self.assertRaises(ValueError):
                    generator.validate_analysis_automatic_motion(packet, controls)

    def test_runtime_native_identity_or_camera_mismatch_cannot_borrow_fitted_drive(self):
        for mismatch in ('hash', 'pts', 'camera'):
            with self.subTest(mismatch=mismatch):
                frame = copy.deepcopy(self.native_frame(3450))
                view = frame['views'][0]
                if mismatch == 'hash':
                    frame['sourceImage']['sha256Bgr8'] = '0' * 64
                elif mismatch == 'pts':
                    frame['decodedTimeSeconds'] += 0.001
                else:
                    view['camera'] = copy.deepcopy(self.generator.candidate['nativeCameraRecord'])
                    view['camera']['verticalFovDegrees'] += 1
                with self.assertRaises(ValueError):
                    self.generator.input(frame, 'bar', view)

    def test_all_207_visible_crank_native_keys_use_chosen_gauge_and_one_fixed_setup(self):
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        fixed = copy.deepcopy(self.generator.analysis_snapshots[0]['chosenInput'])
        fixed['setup']['driveCrankOffsetTurns'] = 0.7118017231396382
        for row in self.visible['frames']:
            with self.subTest(index=row['frameIndex']):
                original = self.native_frame(row['frameIndex'])
                expected = copy.deepcopy(fixed)
                expected['crankTurns'] = -row['relativeCrankTurns'] + 0.7118017231396382
                # Stable consumer API: old main must fail for its actual zero
                # drive, not a missing helper or a changed input signature.
                actual = next(view for view in self.generator.views(original) if view['id'] == 'main')
                self.assertEqual(actual['input'], expected)
                frame = generated[row['timeSeconds']]
                self.assertEqual(frame['shotId'], 'analysis-16')
                self.assertEqual(frame['decodedTimeSeconds'], original['decodedTimeSeconds'])
                self.assertEqual(frame['sourceImage'], {
                    'frameIndex': row['frameIndex'], 'pixelFormat': 'bgr8',
                    **{key: row['sourceImage'][key] for key in ('sourceSha256', 'sha256Bgr8', 'width', 'height')}})
                self.assertEqual(row['sourceImage']['pts'], 1001 * row['frameIndex'])
                self.assertEqual([view['id'] for view in frame['views']], ['main'])
                view = frame['views'][0]
                self.assertEqual(view['input'], expected)
                self.assertEqual(view['presentation'], 'native')
                self.assertEqual(view['rectSourcePixels'], [0, 0, 1920, 1080])
                self.assertEqual(view['camera'], self.gauge['cameraAssociation']['camera'])
        self.assertIsNone(self.visible['authority']['selectedNativeSign'])
        self.assertIsNone(self.visible['authority']['absoluteNativeHomeTurns'])

    def test_visible_crank_source_controls_and_original_observations_are_not_reclassified(self):
        raw = camera_tracks.common.load_observations('6dW6VYXp9HM')
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for row in self.visible['frames']:
            frame = generated[row['timeSeconds']]
            original = next(frame for frame in raw['frames']
                            if frame.get('decodedFrameIndex') == row['frameIndex']
                            and abs(frame['timeSeconds'] - frame['decodedTimeSeconds']) < 1e-9)
            self.assertEqual(frame['landmarks'], [
                {key: point[key] for key in ('anchorId', 'viewId', 'role', 'pixel', 'status', 'method',
                                            'uncertaintyPx', 'trackingEvidence', 'measurementEvidence') if key in point}
                for point in original['landmarks'] if point.get('status') == 'observed' and point.get('pixel') is not None])
            self.assertEqual(self.native_frame(row['frameIndex']).get('views'), original.get('views'))
            self.assertEqual(self.native_frame(row['frameIndex']).get('camera'), original.get('camera'))
            self.assertEqual(self.native_frame(row['frameIndex']).get('unavailable'), original.get('unavailable'))
            if original.get('sourceImage') is not None:
                self.assertEqual(frame['sourceImage'], original['sourceImage'])

    def test_visible_crank_pre_and_post_domain_hold_new_input_until_actual_cut(self):
        first, last = self.visible['frames'][0], self.visible['frames'][-1]
        first_input = copy.deepcopy(self.generator.analysis_snapshots[0]['chosenInput'])
        first_input['setup']['driveCrankOffsetTurns'] = 0.7118017231396382
        first_input['crankTurns'] = 0.7118017231396382
        last_input = copy.deepcopy(first_input)
        last_input['crankTurns'] = -last['relativeCrankTurns'] + 0.7118017231396382
        for frame in self.track['frames']:
            if frame['shotId'] != 'analysis-16':
                continue
            if frame['decodedTimeSeconds'] < first['timeSeconds']:
                self.assertEqual(frame['views'][0]['input'], first_input)
            elif frame['decodedTimeSeconds'] > last['timeSeconds']:
                self.assertEqual(frame['views'][0]['input'], last_input)
        for index, expected in ((2381, first_input), (2607, last_input)):
            frame = self.native_frame(index)
            rendered = next(view for view in self.generator.views(frame) if view['id'] == 'main')
            self.assertEqual(rendered['input'], expected)
        frame = self.native_frame(2608)
        for rendered in self.generator.views(frame):
            self.assertEqual(rendered['input'], self.generator.analysis_snapshots[0]['chosenInput'])

    def test_visible_crank_wrong_shot_view_presentation_or_family_keeps_legacy_input(self):
        for boundary in ('shot', 'view', 'presentation', 'family'):
            with self.subTest(boundary=boundary):
                frame = copy.deepcopy(self.native_frame(2450))
                view = camera_tracks.common.source_views(frame, self.generator.data)[0]
                frame['views'] = [view]
                if boundary == 'shot':
                    frame['shotId'] = 'analysis-17'
                elif boundary == 'view':
                    view['id'] = 'bar-bank'
                elif boundary == 'presentation':
                    view['presentation'] = 'horizontal-mirror'
                else:
                    view['id'] = 'pen-inset'
                rendered = next(row for row in self.generator.views(frame) if row['id'] == view['id'])
                self.assertEqual(rendered['input'], self.generator.analysis_snapshots[0]['chosenInput'])

    def test_visible_crank_interpolates_actual_source_time_and_retains_observed_bottom_noise(self):
        left, right = self.visible['frames'][55:57]
        frame = copy.deepcopy(self.native_frame(left['frameIndex']))
        frame.pop('decodedFrameIndex')
        frame.pop('sourceImage', None)
        frame['decodedTimeSeconds'] = left['timeSeconds'] + 0.25 * (right['timeSeconds'] - left['timeSeconds'])
        frame['timeSeconds'] = 86
        view = camera_tracks.common.source_views(frame, self.generator.data)[0]
        value, _ = self.generator.input(frame, 'cone', view)
        relative = left['relativeCrankTurns'] + 0.25 * (right['relativeCrankTurns'] - left['relativeCrankTurns'])
        self.assertAlmostEqual(value['crankTurns'], -relative + 0.7118017231396382, places=12)
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for row in self.visible['frames']:
            if row['frameIndex'] >= 2512:
                self.assertEqual(generated[row['timeSeconds']]['views'][0]['input']['crankTurns'],
                                 -row['relativeCrankTurns'] + 0.7118017231396382)

    def test_visible_crank_semantic_identity_and_unresolved_source_sign_are_required(self):
        for mismatch in ('missing-frame', 'frame-index', 'pts', 'hash', 'format', 'time',
                         'turns', 'selected-sign', 'home', 'phase-transfer', 'source-conflict'):
            with self.subTest(mismatch=mismatch):
                packet = copy.deepcopy(self.visible)
                generator = copy.copy(self.generator)
                row = packet['frames'][40]
                if mismatch == 'missing-frame':
                    packet['frames'].pop(40)
                elif mismatch == 'frame-index':
                    row['frameIndex'] += 1
                elif mismatch == 'pts':
                    row['sourceImage']['pts'] += 1
                elif mismatch == 'hash':
                    row['sourceImage']['sha256Bgr8'] = 'not-a-hash'
                elif mismatch == 'format':
                    row['sourceImage']['format'] = 'gray8'
                elif mismatch == 'time':
                    row['timeSeconds'] += 0.001
                elif mismatch == 'turns':
                    row['relativeCrankTurns'] = float('nan')
                elif mismatch == 'selected-sign':
                    packet['authority']['selectedNativeSign'] = -1
                elif mismatch == 'home':
                    packet['authority']['absoluteNativeHomeTurns'] = 0.7118017231396382
                elif mismatch == 'phase-transfer':
                    packet['authority']['phaseTransferToOtherShots'] = True
                else:
                    generator.data = {**generator.data, 'frames': [
                        {**frame, 'sourceImage': {**frame['sourceImage'], 'sha256Bgr8': '0' * 64}}
                        if frame.get('decodedFrameIndex') == row['frameIndex'] else frame
                        for frame in generator.data['frames']]}
                with self.assertRaises(ValueError):
                    generator.validate_analysis_visible_crank(packet)

    def test_visible_crank_missing_legacy_images_gain_only_exact_authority_identities(self):
        data = camera_tracks.common.load_observations('6dW6VYXp9HM')
        index = 2450
        originals = [copy.deepcopy(frame) for frame in data['frames'] if frame.get('decodedFrameIndex') == index]
        for frame in data['frames']:
            if frame.get('decodedFrameIndex') == index:
                frame.pop('sourceImage', None)
        with patch.object(camera_tracks.common, 'load_observations', return_value=data):
            generator = camera_tracks.Generator('6dW6VYXp9HM')
        authority = next(row for row in self.visible['frames'] if row['frameIndex'] == index)
        generated = [frame for frame in generator.data['frames'] if frame.get('decodedFrameIndex') == index]
        for before, after in zip(originals, generated):
            self.assertEqual(after['sourceImage'], camera_tracks.visible_crank_source_image(authority))
            self.assertEqual({key: value for key, value in after.items() if key != 'sourceImage'},
                             {key: value for key, value in before.items() if key != 'sourceImage'})

    def test_visible_crank_missing_or_corrupt_source_and_gauge_artifacts_refuse(self):
        paths = (camera_tracks.VISIBLE_CRANK_MOTION, camera_tracks.VISIBLE_CRANK_GAUGE)
        for target in paths:
            for missing in (False, True):
                with self.subTest(target=target, missing=missing), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    for path in paths:
                        if path == target and missing:
                            continue
                        destination = root / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        data = (camera_tracks.ROOT / path).read_bytes()
                        destination.write_bytes(data + b' ' if path == target else data)
                    with patch.object(camera_tracks, 'ROOT', root), self.assertRaises(ValueError):
                        self.generator.analysis_visible_crank_packet()

    def test_visible_crank_gauge_cannot_promote_source_sign_or_change_camera_setup_math(self):
        for mismatch in ('native-sign', 'offset', 'lag', 'historical-sign', 'camera',
                         'phase', 'math', 'model', 'stage', 'source-sign', 'positive-control'):
            with self.subTest(mismatch=mismatch):
                gauge = copy.deepcopy(self.gauge)
                if mismatch == 'native-sign':
                    gauge['chosenGauge']['nativeSign'] = 1
                elif mismatch == 'offset':
                    gauge['chosenGauge']['shotLocalOffsetTurns'] = 0
                elif mismatch == 'lag':
                    gauge['chosenGauge']['driveCrankOffsetTurns'] = 0
                elif mismatch == 'historical-sign':
                    gauge['chosenGauge']['historicalNativeSignIdentified'] = True
                elif mismatch == 'camera':
                    gauge['cameraAssociation']['camera']['verticalFovDegrees'] += 1
                elif mismatch == 'phase':
                    gauge['baseChosenInput']['phases'][0] += 0.1
                elif mismatch == 'math':
                    gauge['nativeMathSha256']['web/src/mechanics.ts'] = '0' * 64
                elif mismatch == 'model':
                    gauge['modelSha256'] = '0' * 64
                elif mismatch == 'stage':
                    gauge['qualification']['stageAcceptance'] = True
                elif mismatch == 'source-sign':
                    gauge['qualification']['sourceSelectedNativeSign'] = -1
                else:
                    gauge['positiveControls'][0]['projectedDirection'] = 'clockwise'
                with self.assertRaises(ValueError):
                    self.generator.validate_analysis_visible_crank_gauge(self.visible, gauge)

    def test_visible_crank_runtime_native_identity_and_camera_mismatches_refuse(self):
        for mismatch in ('hash', 'pts', 'camera'):
            with self.subTest(mismatch=mismatch):
                frame = copy.deepcopy(self.native_frame(2450))
                view = camera_tracks.common.source_views(frame, self.generator.data)[0]
                if mismatch == 'hash':
                    frame['sourceImage']['sha256Bgr8'] = '0' * 64
                elif mismatch == 'pts':
                    frame['decodedTimeSeconds'] += 0.001
                else:
                    view['camera'] = copy.deepcopy(self.gauge['cameraAssociation']['camera'])
                    view['camera']['verticalFovDegrees'] += 1
                with self.assertRaises(ValueError):
                    self.generator.input(frame, 'cone', view)

    def test_visible_crank_diagnostics_separate_observed_source_and_chosen_native_gauge(self):
        diagnostics = self.track['cpuDiagnostics']['analysisVisibleCrankMotion']
        self.assertEqual(diagnostics['domain']['measurementStatus'], 'observed-cycles-approximate-within-cycle-phase')
        self.assertEqual(diagnostics['domain']['startSeconds'], self.visible['interval']['startSeconds'])
        self.assertEqual(diagnostics['domain']['endSeconds'], self.visible['interval']['endSeconds'])
        self.assertEqual([hold['kind'] for hold in diagnostics['sameShotMarginHolds']],
                         ['chosen-first-input-hold', 'chosen-last-input-hold'])
        self.assertTrue(all(hold['measurementStatus'] == 'unmeasured'
                            for hold in diagnostics['sameShotMarginHolds']))
        self.assertEqual(diagnostics['sourceAuthority'], self.visible['authority'])
        self.assertIsNone(diagnostics['sourceAuthority']['selectedNativeSign'])
        self.assertIsNone(diagnostics['sourceAuthority']['absoluteNativeHomeTurns'])
        self.assertEqual(diagnostics['chosenGauge']['nativeSign'], -1)
        self.assertFalse(diagnostics['chosenGauge']['historicalNativeSignIdentified'])
        self.assertFalse(diagnostics['chosenGauge']['historicalNativeHomeIdentified'])
        self.assertFalse(diagnostics['cameraAssociation']['sourceNativeCameraQualified'])
        self.assertFalse(diagnostics['qualification']['stageAcceptance'])


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
