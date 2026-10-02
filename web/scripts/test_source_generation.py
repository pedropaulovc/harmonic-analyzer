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
camera_tracks = load_script('generate-analysis-synthesis-source-tracks.py', 'source_generation_camera_tracks')


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

    def test_opaque_main_retains_real_unscoped_alias_check(self):
        data = exact_exposure()
        for frame in data['frames']:
            frame['views'] = [{'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080],
                               'presentation': 'native', 'composite': {'mode': 'opaque'}}]
        retained_point = {'anchorId': 'base', 'status': 'observed', 'role': 'fit',
                          'pixel': [80, 420]}
        data['frames'][0]['landmarks'] = [retained_point]
        result = retain(data)
        self.assertEqual({p['anchorId']: (p['role'], p['pixel']) for p in result['landmarks']},
                         {'base': ('fit', [80, 420]), 'support': ('check', [120.5, 340.25])})
        self.assertEqual(result['views'], data['frames'][0]['views'])
        self.assertEqual(data['samplingDiagnostics']['exactExposureAliasLandmarks']['unavailable'], [])

    def test_unscoped_opaque_check_cannot_cross_different_source_layout(self):
        for mismatch in ('rect', 'presentation', 'warp', 'crossfade', 'inset'):
            with self.subTest(mismatch=mismatch):
                data = exact_exposure()
                for frame in data['frames']:
                    frame['views'] = [{'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080],
                                       'presentation': 'native', 'composite': {'mode': 'opaque'}}]
                donor = data['frames'][1]['views'][0]
                if mismatch == 'rect':
                    donor['rectSourcePixels'] = [0, 0, 960, 1080]
                elif mismatch == 'presentation':
                    donor['presentation'] = 'horizontal-mirror'
                elif mismatch == 'warp':
                    donor['imagePlaneWarp'] = {
                        'kind': 'homography', 'unwarpedViewportPixels': [1920, 1080],
                        'renderToSourcePixels': [1, 0, 10, 0, 1, 0, 0, 0, 1]}
                elif mismatch == 'crossfade':
                    donor['composite'] = {'mode': 'crossfade', 'groupId': 'fade',
                                          'imageLayerId': 'incoming', 'opacity': 0.5}
                else:
                    data['frames'][1]['views'].append(
                        {'id': 'inset', 'rectSourcePixels': [0, 0, 640, 360]})
                self.assertEqual(retain(data)['landmarks'], [])

    def test_equal_transition_or_warped_layout_cannot_scope_legacy_points(self):
        for transformed in ('crossfade', 'warp', 'mirror', 'inset'):
            with self.subTest(transformed=transformed):
                data = exact_exposure()
                view = {'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080],
                        'presentation': 'native', 'composite': {'mode': 'opaque'}}
                if transformed == 'crossfade':
                    view['composite'] = {'mode': 'crossfade', 'groupId': 'fade',
                                         'imageLayerId': 'incoming', 'opacity': 0.5}
                elif transformed == 'warp':
                    view['imagePlaneWarp'] = {
                        'kind': 'homography', 'unwarpedViewportPixels': [1920, 1080],
                        'renderToSourcePixels': [1, 0, 10, 0, 1, 0, 0, 0, 1]}
                elif transformed == 'mirror':
                    view['presentation'] = 'horizontal-mirror'
                for frame in data['frames']:
                    frame['views'] = [copy.deepcopy(view)]
                    if transformed == 'inset':
                        frame['views'].append({'id': 'inset', 'rectSourcePixels': [0, 0, 640, 360]})
                self.assertEqual(retain(data)['landmarks'], [])

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
def operation_exposure():
    data, rocker_seeds = rocker_exposure()
    data['source']['videoId'] = 'jfH-NbsmvD4'
    data['shots'][0]['id'] = 'operation-019'
    frame = data['frames'][0]
    frame.update(shotId='operation-019', sourceFrameIndex=30,
                 sourceImage=copy.deepcopy(rocker_seeds['states'][0]['sourceImage']),
                 sourceObservationAuthority='operation019-v3',
                 unavailable=[{'anchorId': 'lost-feature', 'viewId': 'main',
                               'reason': 'Inherited source loss remains unqualified.'}])
    frame['camera'] = copy.deepcopy(rocker_seeds['bodyCandidate']['camera'])
    frame['landmarks'] = [{'anchorId': 'support', 'role': 'check',
                           'status': 'observed', 'method': 'manual',
                           'pixel': [120.5, 340.25], 'uncertaintyPx': 3}]
    data['anchors'] = [{'id': 'support', 'kind': 'physical-feature'}]
    old_input = copy.deepcopy(rocker_seeds['states'][0]['completeInput'])
    new_input = copy.deepcopy(old_input)
    new_input['crankTurns'] = 0.75
    camera = copy.deepcopy(frame['camera'])
    camera['positionMetres'] = [0, 0, 3]
    seeds = {
        'sourceInputIndex': {'rows': [{
            'recordId': 'canonical:0:main', 'kind': 'canonical',
            'shotId': 'operation-019', 'timeSeconds': 1.01,
            'sourceFrameIndex': 30, 'viewId': 'main',
            'rectSourcePixels': [0, 0, 1920, 1080]}]},
        'chosenStates': {'canonical:0:main': old_input},
        'observedDegrees': {}, 'fragments': {}, 'gapExposures': [],
        'correctedCaptures': {},
        'sourceControls': [{
            'sourceFrameIndex': 30, 'sourceImage': copy.deepcopy(frame['sourceImage']),
            'declarations': [{
                'fragment': 'historical', 'viewId': 'main',
                'usage': 'provenance-only',
                'declaration': {**copy.deepcopy(frame['landmarks'][0]),
                                'pixel': [140, 360]}}]}],
        'captureRequests': [{'path': 'tracked-numeric-seed', 'request': {
            'sourceImage': copy.deepcopy(frame['sourceImage']),
            'decodedTimeSeconds': 1.0, 'viewId': 'main', 'camera': camera,
            'input': new_input, 'cameraContinuityFamily': 'conditional-family',
            'cameraProvenance': {'kind': 'source-fit', 'family': 'conditional-family',
                                 'evidence': 'CHECK-informed inherited family; not cold.'},
            'inputEvidence': 'Chosen complete state; hidden input is unobserved.'}}],
    }
    return data, seeds


class OperationCaptureAuthorityTests(unittest.TestCase):
    def generate(self, data, seeds):
        with patch.object(rocker.common, 'load_observations',
                          return_value=copy.deepcopy(data)), patch.object(
                rocker, 'load_seeds', return_value=(copy.deepcopy(seeds), {})), patch.object(
                rocker, 'retain_generator_inputs'):
            return rocker.operation()

    def test_fresh_pixels_and_inherited_loss_survive_complete_playback(self):
        data, seeds = operation_exposure()
        track = self.generate(data, seeds)
        for time in (1, 1.01):
            frame = next(row for row in track['frames'] if row['timeSeconds'] == time)
            self.assertEqual(frame['landmarks'], data['frames'][0]['landmarks'])
            self.assertEqual(frame['unavailable'], data['frames'][0]['unavailable'])
            self.assertEqual(frame['decodedTimeSeconds'], 1.0)
            self.assertEqual(frame['sourceImage'], data['frames'][0]['sourceImage'])
            self.assertEqual(frame['views'][0]['input']['crankTurns'], 0.75)
            self.assertEqual(frame['views'][0]['camera']['positionMetres'], [0, 0, 3])

    def test_different_source_hash_clock_or_view_cannot_replace_exact_camera_input(self):
        for mismatch in ('hash', 'source', 'pts', 'view'):
            with self.subTest(mismatch=mismatch):
                data, seeds = operation_exposure()
                request = seeds['captureRequests'][0]['request']
                if mismatch == 'hash':
                    request['sourceImage']['sha256Gray8'] = 'c' * 64
                elif mismatch == 'source':
                    request['sourceImage']['sourceSha256'] = 'c' * 64
                elif mismatch == 'pts':
                    request['decodedTimeSeconds'] = 1.00001
                else:
                    request['viewId'] = 'inset'
                track = self.generate(data, seeds)
                frame = next(row for row in track['frames'] if row['timeSeconds'] == 1)
                self.assertEqual(frame['views'][0]['camera'], data['frames'][0]['camera'])
                self.assertEqual(frame['views'][0]['input']['crankTurns'], 0)
                self.assertEqual(frame['landmarks'], data['frames'][0]['landmarks'])


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
