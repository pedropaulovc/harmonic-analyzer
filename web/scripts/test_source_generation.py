"""Consumer-visible source identity and presentation refusal boundaries."""
import copy
from contextlib import contextmanager
import importlib.util
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
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
intro = load_script('generate-intro-source-track.py', 'source_generation_intro')
camera_tracks = load_script(os.environ.get('SOURCE_GENERATOR_PATH',
                                          'generate-analysis-synthesis-source-tracks.py'),
                            'source_generation_camera_tracks')


HISTORICAL_SCENE_SHA256 = '7b28468cc3f36a2e4d3699e252c54df837770868481c83a486b572a32f6b3b8b'


def historical_scene_bytes():
    # Exact git blob cad3a39e17fe912b8143e6ed4ed9946cfe6869a1 from
    # 1af315999:web/src/scene.ts, retained in the sealed canonical archive.
    return common.historical_code_bytes('web/src/scene.ts', HISTORICAL_SCENE_SHA256)


@contextmanager
def replay_source_bytes(sources):
    """Scope actual source bytes to intended ROOT paths, never override seals."""
    fixtures = {camera_tracks.ROOT / relative: data for relative, data in sources.items()}
    read_bytes, read_text = Path.read_bytes, Path.read_text

    def read_source(path):
        return fixtures[path] if path in fixtures else read_bytes(path)

    def read_source_text(path, encoding=None, errors=None, **kwargs):
        if path not in fixtures:
            return read_text(path, encoding=encoding, errors=errors, **kwargs)
        with io.TextIOWrapper(io.BytesIO(fixtures[path]), encoding=encoding,
                              errors=errors, **kwargs) as source:
            return source.read()

    with patch.object(Path, 'read_bytes', read_source), \
            patch.object(Path, 'read_text', read_source_text):
        yield


def historical_synthesis_dependencies():
    """Exact old producer/math bytes, not a claim about today's source files."""
    packet = json.loads((HERE.parent / 'content/canonical-native/8KmVDxkia_w.automatic-motion.json').read_bytes())
    return {path: common.historical_code_bytes(path, record['sha256'])
            for path, record in packet['generationDependencies'].items()
            if not path.startswith('web/content/')}


def historical_synthesis_generator():
    # Replay retained source/input calibration, not current renderer/model/GPU
    # approval. The constructor reads all four code dependencies plus scene.ts;
    # both byte seals and native-data text see the same actual archived bytes.
    sources = historical_synthesis_dependencies()
    sources['web/src/scene.ts'] = historical_scene_bytes()
    with replay_source_bytes(sources):
        return camera_tracks.Generator('8KmVDxkia_w')


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


class ObservationStorageBoundaryTests(unittest.TestCase):
    def test_bad_or_missing_gzip_never_uses_plain_canonical_sibling(self):
        valid = gzip.compress(b'{"frames": []}', mtime=0)
        bad_crc = valid[:-8] + bytes([valid[-8] ^ 1]) + valid[-7:]
        cases = (
            ('missing', None, FileNotFoundError),
            ('bad-header', b'not a gzip stream', gzip.BadGzipFile),
            ('truncated', valid[:-8], EOFError),
            ('bad-crc', bad_crc, gzip.BadGzipFile),
            ('invalid-json', gzip.compress(b'{"frames":', mtime=0), json.JSONDecodeError),
        )
        for label, stored, error in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                web = Path(directory)
                content = web / 'content' / 'canonical-native'
                content.mkdir(parents=True)
                (content / 'fixture.observations.json').write_text('{"frames": []}')
                if stored is not None:
                    (content / 'fixture.observations.json.gz').write_bytes(stored)
                with patch.object(common, 'WEB', web), self.assertRaises(error):
                    common.load_observations('fixture')

    def test_plain_canonical_observation_output_is_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            content = web / 'content' / 'canonical-native'
            content.mkdir(parents=True)
            path = content / 'fixture.observations.json'
            with patch.object(common, 'WEB', web), self.assertRaisesRegex(
                    ValueError, 'Canonical observation output must end in'):
                common.write_observations(path, {'frames': []})
            self.assertFalse(path.exists())




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
    approved = json.loads((rocker.WEB / 'content/model-representation.json').read_bytes())
    data.update(model=copy.deepcopy(approved['source']), anchors=[])
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
            return historical_synthesis_generator()

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
        permission_path = camera_tracks.WEB / 'content/canonical-native/8KmVDxkia_w.chosen-camera-continuity.json'
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
        content = HERE.parent / 'content' / 'canonical-native'
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

        proof_path = 'web/src/mechanics.ts'
        hashes = self.packet['diagnostics']['nativeForwardSmoke']['nativeMathSha256']
        for missing in (False, True):
            with self.subTest(historical_snapshot='missing' if missing else 'modified'), \
                    tempfile.TemporaryDirectory() as directory:
                web = Path(directory)
                for path, digest in hashes.items():
                    if path == proof_path and missing:
                        continue
                    target = web / 'content/canonical-native/historical-code' / digest / Path(path).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    raw = common.historical_code_bytes(path, digest)
                    target.write_bytes(raw + b'\n' if path == proof_path else raw)
                reason = 'unavailable' if missing else 'changed'
                with patch.object(camera_tracks.common, 'WEB', web), \
                        self.assertRaisesRegex(ValueError, f'Historical producer snapshot {reason}: {proof_path}$'):
                    self.generator.validate_analysis_automatic_motion(self.packet, self.controls)

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


class OrdinaryProducerLiveGuardTests(unittest.TestCase):
    @contextmanager
    def live_fixture(self, module, video_id):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / 'web'
            def store(path, raw):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            producer = 'web/scripts/' + Path(module.__file__).name
            paths = [
                producer, 'web/scripts/compact-source-common.py', 'web/src/bindings.ts', 'web/src/scene.ts',
                'web/src/mechanics.ts', 'web/src/mechanics-data.ts', 'web/src/magnifier.ts', 'web/src/kinematics.ts',
            ]
            seals = []
            for path in paths:
                raw = (HERE.parents[1] / path).read_bytes()
                sha = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
                store(path, raw)
                seals.append({'path': path, 'sha256': sha})
                # Even a matching SHA-addressed archive cannot replace a missing
                # or altered live path during ordinary generation.
                store('web/content/canonical-native/historical-code/' + hashlib.sha256(raw).hexdigest()
                      + '/' + Path(path).name, raw)
            store('web/content/canonical-native/manifest.json', json.dumps({
                'canonicalConsumerHashNormalization': 'CRLF-to-LF',
                'canonicalConsumerInputs': seals, 'historicalCodeSnapshots': [],
            }).encode('utf8'))
            approved = (HERE.parent / 'content/model-representation.json').read_bytes()
            store('web/content/model-representation.json', approved)
            source_model = json.loads(approved)['source']
            data = {
                'source': {'videoId': video_id, 'sha256': 'b' * 64, 'width': 1920, 'height': 1080,
                           'durationSeconds': 1, 'fps': {'numerator': 1, 'denominator': 1}},
                'model': {**source_model, 'units': 'metres', 'axes': 'X-width/Y-height/Z-depth'},
                'anchors': [{'id': 'gta.paper.screw17',
                             'partPath': 'ha-harmonic-analyzer/pd-paper-drive/vn-fillister-screw-17',
                             'partLocalMetres': [0, 0, 0], 'correspondenceEvidence': 'Source marker'}],
                'shots': [{'id': 'machine', 'startSeconds': 0, 'endSeconds': 1,
                           'classification': 'machine', 'hasCorrespondingMachine': True}],
                'frames': [{'timeSeconds': 0, 'decodedTimeSeconds': 0, 'shotId': 'machine',
                            'classification': 'machine', 'landmarks': [],
                            'views': [{'id': 'main', 'presentation': 'native',
                                       'rectSourcePixels': [0, 0, 1920, 1080]}]}],
                'sourceCameraRigs': [{'id': 'fixture-phase-rig', 'measurements': []}],
            }
            phase_path = 'web/content/canonical-native/XPQwKRt4Y2k.source-phase-map.json'
            phase_bytes = json.dumps({'rigId': 'fixture-phase-rig', 'references': [], 'sourceFrameMap': []}).encode('utf8')
            store(phase_path, phase_bytes)
            seeds = {
                'views': {'main': {'candidateId': 'fixture', 'camera': {
                    'positionMetres': [0, 0, 1], 'quaternion': [0, 0, 0, 1], 'verticalFovDegrees': 45}}},
                'candidates': {'fixture': {
                    'packet': 'fixture-source-choice', 'sha256': 'c' * 64, 'unobservedInputFields': [],
                    'input': {'crankTurns': 0, 'amplitudes': [0] * 20, 'phases': [0] * 20,
                              'gearing': 'medium-medium', 'magnification': 1,
                              'setup': {key: 0 for key in common.SETUP_FIELDS}}}},
                'montageSourceControls': {'anchors': [], 'frames': [], 'method': 'fixture-source-only',
                                         'qualification': 'unmeasured', 'summary': {}, 'trackingFailures': []},
                'staticSourceFamily': {
                    'id': 'fixture-phase-rig', 'kind': 'source-static', 'sourceSha256': 'b' * 64,
                    'phaseImages': [], 'independentSourcePhaseMap': {
                        'path': phase_path, 'sha256': hashlib.sha256(phase_bytes).hexdigest()}},
                'staticMotion': {'shotAmendments': []}, 'physicalSourceCrossfades': {'frames': {}},
                'sourceMeasurementLimits': {'guide': 'No measured guide controls.'},
            }
            store('web/content/canonical-native/XPQwKRt4Y2k.source-seeds.json', json.dumps(seeds).encode('utf8'))
            observation = web / 'content/canonical-native' / f'{video_id}.observations.json.gz'
            output = web / 'content' / f'{video_id}.source-track.json'
            store(output.relative_to(root), b'{"previous":"must-survive-refusal"}\n')
            with patch.object(module.common, 'WEB', web), patch.object(module, '__file__', str(root / producer)):
                module.common.native_motion_bindings.cache_clear()
                try:
                    observation.write_bytes(gzip.compress(json.dumps(data).encode('utf8'), mtime=0))
                    yield root, data, observation, output, paths
                finally:
                    module.common.native_motion_bindings.cache_clear()

    def test_old_source_refuses_intro_and_spin_without_publishing(self):
        for module, video_id in ((intro, 'NAsM30MAHLg'), (spin, 'XPQwKRt4Y2k')):
            with self.subTest(video=video_id), self.live_fixture(module, video_id) as (_, data, source, output, _):
                data['model'].update(
                    sha256='2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d',
                    sourceCommit='1268c23d4a8fc741147c5e09d8d1e45247a71945')
                source.write_bytes(gzip.compress(json.dumps(data).encode('utf8'), mtime=0))
                previous = output.read_bytes()
                with self.assertRaisesRegex(ValueError, 'independently approved live model'):
                    module.main()
                self.assertEqual(output.read_bytes(), previous)

    def test_fresh_intro_and_spin_publish_but_live_renderer_drift_cannot_borrow_archive(self):
        for module, video_id in ((intro, 'NAsM30MAHLg'), (spin, 'XPQwKRt4Y2k')):
            with self.subTest(video=video_id), self.live_fixture(module, video_id) as (root, data, _, output, paths):
                module.main()
                published = output.read_bytes()
                track = json.loads(published)
                self.assertEqual(track['model'], data['model'])
                self.assertIsNone(track['anchors'][0]['motion'])
                self.assertEqual(track['frames'][0]['views'][0]['input']['gearing'],
                                 'small-large' if module is intro else 'medium-medium')
                for path in paths:
                    live_path = root / path
                    sealed = live_path.read_bytes()
                    for mutation in ('changed', 'missing'):
                        with self.subTest(path=path, mutation=mutation):
                            if mutation == 'changed':
                                live_path.write_bytes(sealed + b'\n')
                            else:
                                live_path.unlink()
                            try:
                                with self.assertRaisesRegex(ValueError, 'live producer input (differs|unavailable)'):
                                    module.main()
                                self.assertEqual(output.read_bytes(), published)
                            finally:
                                live_path.write_bytes(sealed)

    def test_analysis_synthesis_cli_checks_entire_pair_before_generation(self):
        with self.live_fixture(camera_tracks, '6dW6VYXp9HM') as (root, data, _, output, _):
            old_synthesis = copy.deepcopy(data)
            old_synthesis['source']['videoId'] = '8KmVDxkia_w'
            old_synthesis['model'].update(
                sha256='2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d',
                sourceCommit='1268c23d4a8fc741147c5e09d8d1e45247a71945')
            synthesis = root / 'web/content/canonical-native/8KmVDxkia_w.observations.json.gz'
            synthesis.write_bytes(gzip.compress(json.dumps(old_synthesis).encode('utf8'), mtime=0))
            second_output = root / 'web/content/8KmVDxkia_w.source-track.json'
            second_output.write_bytes(b'{"previous":"second-must-survive"}\n')
            before = output.read_bytes(), second_output.read_bytes()
            script = root / 'web/scripts' / Path(camera_tracks.__file__).name
            with patch('sys.argv', [str(script)]), self.assertRaisesRegex(
                    ValueError, 'independently approved live model'):
                runpy.run_path(str(script), run_name='__main__')
            self.assertEqual((output.read_bytes(), second_output.read_bytes()), before)


class SpinPresentationTests(unittest.TestCase):
    def assert_seed_refused_before_observations(self, seed):
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            (web / 'content' / 'canonical-native').mkdir(parents=True)
            (web / 'content' / 'canonical-native' / 'XPQwKRt4Y2k.source-seeds.json').write_text(
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


class SynthesisAutomaticSourceDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the actual consumer constructor, including inline retained native
        # calibration, rather than assuming every calibration record is a file.
        cls.generator = historical_synthesis_generator()
        cls.track = cls.generator.build()
        cls.baseline = common.compact_input(cls.generator.base)
        cls.native_frames = {
            frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')): frame
            for frame in cls.generator.data['frames']
            if frame.get('decodedTimeSeconds') is not None
            and abs(frame['timeSeconds'] - frame['decodedTimeSeconds']) < 1e-8
        }
        # These fixtures remain beside the tests when SOURCE_GENERATOR_PATH
        # selects an exact historical producer copied to a sibling file.
        content = HERE.parent / 'content' / 'canonical-native'
        cls.packet = json.loads((content / '8KmVDxkia_w.automatic-motion.json').read_text())
        cls.candidate = next(row for row in cls.packet['bankCandidates']
                             if row['id'] == 'bank-direction-+1')

    def source_frame(self, index):
        return self.native_frames[index]

    def main_input(self, frame):
        return next(view['input'] for view in self.generator.views(frame)
                    if view['id'] == 'main')

    def assert_complete_input(self, value, turns):
        self.assertAlmostEqual(value['crankTurns'], turns, places=10)
        expected = copy.deepcopy(self.baseline)
        expected['phases'] = self.candidate['staticPhasesRad']
        expected['setup'].update(self.candidate['requiredSetup'])
        for field in ('amplitudes', 'phases', 'gearing', 'magnification', 'setup'):
            self.assertEqual(value[field], expected[field], field)

    def test_cumulative_source_drive_wins_over_old_single_rocker_fold(self):
        first, last = self.source_frame(2541), self.source_frame(2973)
        a, b = self.main_input(first), self.main_input(last)
        # This assertion fails on original main's consumer-visible parked crank,
        # before accessing any API or constant introduced by automatic motion.
        self.assertGreater(b['crankTurns'] - a['crankTurns'], 27)
        self.assertEqual(a['phases'], b['phases'])
        self.assertEqual(len(set(a['phases'])), 1)
        self.assertEqual(len(a['phases']), 20)
        fps = self.packet['source']['fps']
        rate = fps['numerator'] / fps['denominator']
        for knot in self.candidate['knots']:
            index = round(knot['timeSeconds'] * rate)
            with self.subTest(index=index):
                self.assert_complete_input(self.main_input(self.source_frame(index)),
                                           knot['crankTurns'])
        # Also exercise serialization and the real integer playback aliases;
        # the drive belongs to the retained exposure, not its rounded label.
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for label, original, value in ((106, first, a), (124, last, b)):
            with self.subTest(label=label):
                frame = generated[label]
                self.assertEqual(frame['decodedTimeSeconds'], original['decodedTimeSeconds'])
                self.assertEqual(frame['sourceImage'], original['sourceImage'])
                bank = next(view for view in frame['views'] if view['id'] == 'main')
                self.assertEqual(bank['input'], value)

    def test_between_knots_interpolation_does_not_wrap_or_park_the_crank(self):
        before, after = self.source_frame(2579), self.source_frame(2581)
        middle = self.source_frame(2580)  # Independent CHECK, excluded from knot FIT.
        a, b, m = (self.main_input(frame) for frame in (before, after, middle))
        self.assertNotIn(middle['decodedTimeSeconds'],
                         [knot['timeSeconds'] for knot in self.candidate['knots']])
        self.assertGreater(a['crankTurns'], 1)
        self.assertLess(a['crankTurns'], m['crankTurns'])
        self.assertLess(m['crankTurns'], b['crankTurns'])
        expected_turns = (a['crankTurns'] + b['crankTurns']) / 2
        self.assert_complete_input(m, expected_turns)

    def test_interval_edges_hold_in_same_shot_but_never_cross_the_cut(self):
        first, end = self.source_frame(2541), self.source_frame(2983)
        end_input = self.main_input(end)
        # Comparing against source authority (not another parked output) catches
        # missing cumulative drive as well as an endpoint return-to-zero blend.
        self.assert_complete_input(end_input, self.candidate['knots'][-1]['crankTurns'])
        before_input = self.main_input(self.source_frame(2540))
        self.assert_complete_input(before_input, self.candidate['knots'][0]['crankTurns'])
        self.assertEqual(before_input, self.main_input(first))
        shot_end = self.generator.shots['rocker-bank']['endSeconds']
        for time in ((end['decodedTimeSeconds'] + shot_end) / 2, shot_end - 1e-6):
            with self.subTest(time=time):
                boundary = copy.deepcopy(end)
                # Mathematical instants, not extra observations/source identities.
                for field in ('sourceImage', 'sourceFrameIndex', 'decodedFrameIndex'):
                    boundary.pop(field, None)
                boundary['timeSeconds'] = boundary['decodedTimeSeconds'] = time
                self.assertEqual(self.main_input(boundary), end_input)
        next_shot = self.source_frame(2984)
        self.assertEqual(next_shot['shotId'], 'rocker-out')
        self.assertEqual(self.main_input(next_shot)['crankTurns'], self.baseline['crankTurns'])


class SynthesisAutomaticSourceDriveCurrentOnlyTests(unittest.TestCase):
    def fixture(self, load_motion=True):
        generator = historical_synthesis_generator()
        if not load_motion:
            generator.synthesis_automatic_motion = None
        return generator

    def source_frame(self, generator, index):
        return next(frame for frame in generator.data['frames']
                    if frame['shotId'] == 'rocker-bank'
                    and frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')) == index)

    def main_view(self, generator, frame):
        return next(view for view in common.source_views(frame, generator.data)
                    if view['id'] == 'main')

    def test_current_only_no_bank_drive_leaks_to_other_shots_views_or_camera_layers(self):
        generator = self.fixture()
        frame = self.source_frame(generator, 2700)
        view = self.main_view(generator, frame)
        for scope in ('other-shot', 'wrong-family', 'inset', 'mirror', 'warp', 'composite', 'other-corpus'):
            with self.subTest(scope=scope):
                row, source_view, family = copy.deepcopy(frame), copy.deepcopy(view), 'bar'
                if scope == 'other-shot':
                    row['shotId'] = 'rocker-out'
                elif scope == 'wrong-family':
                    family = 'cone'
                elif scope == 'inset':
                    source_view['id'] = 'lower-inset'
                    source_view['rectSourcePixels'] = [0, 0, 960, 1080]
                elif scope == 'mirror':
                    source_view['presentation'] = 'horizontal-mirror'
                elif scope == 'warp':
                    source_view['imagePlaneWarp'] = {'kind': 'homography',
                        'unwarpedViewportPixels': [0, 0, 1920, 1080],
                        'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]}
                elif scope == 'composite':
                    source_view['composite'] = {'mode': 'crossfade'}
                elif scope == 'other-corpus':
                    generator.data['source']['videoId'] = '6dW6VYXp9HM'
                self.assertIsNone(generator.synthesis_automatic_input(row, family, source_view))

    def test_current_only_interval_refuses_exact_cut(self):
        generator = self.fixture()
        end = self.source_frame(generator, 2983)
        boundary = copy.deepcopy(end)
        boundary['decodedTimeSeconds'] = generator.shots['rocker-bank']['endSeconds']
        self.assertIsNone(generator.synthesis_automatic_input(
            boundary, 'bar', self.main_view(generator, end)))

    def test_current_only_h1_pixel_holdout_accepts_fit_times_but_refuses_exposure_holdout(self):
        generator = self.fixture()
        packet = generator.synthesis_automatic_motion['packet']
        evidence = json.loads((camera_tracks.ROOT / camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE).read_text())
        annotation_fits = {row['sourceImage']['frameIndex'] for row in evidence['annotations']
                           if row['role'] == 'fit'}
        h1_checks = [row for row in evidence['nearestJointSource']['rows'] if row['role'] == 'check']
        self.assertEqual(len(h1_checks), 17)
        self.assertTrue({row['sourceImage']['frameIndex'] for row in h1_checks} <= annotation_fits)
        # A valid cross-feature CHECK exposure must retain its annotation cadence
        # knot, not be dropped by an overbroad all-physical exposure holdout.
        knots = {row['timeSeconds']: row['crankTurns']
                 for row in generator.synthesis_automatic_motion['candidate']['knots']}
        for row in h1_checks:
            with self.subTest(accepted_h1_frame=row['sourceImage']['frameIndex']):
                frame = self.source_frame(generator, row['sourceImage']['frameIndex'])
                value, _ = generator.synthesis_automatic_input(
                    frame, 'bar', self.main_view(generator, frame))
                self.assertAlmostEqual(value['crankTurns'], knots[row['timeSeconds']], places=10)

        paths = [camera_tracks.SYNTHESIS_AUTOMATIC_MOTION, *packet['generationDependencies']]
        sealed_sources = historical_synthesis_dependencies()
        for mismatch in ('h1-exposure-authority', 'h1-disjoint-time', 'h20-fit-overlap'):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for relative in paths:
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(sealed_sources[relative] if relative in sealed_sources
                                       else (camera_tracks.ROOT / relative).read_bytes())
                changed_packet, changed_evidence = copy.deepcopy(packet), copy.deepcopy(evidence)
                expected_error = 'H1 CHECK feature-pixel holdout'
                if mismatch == 'h1-exposure-authority':
                    changed_packet['bankMeasurement']['physicalCHECKHoldout']['nearest1PhysicalJoint'] = (
                        'exposure-disjoint-from-annotation-FIT')
                else:
                    if mismatch == 'h1-disjoint-time':
                        changed_row = next(row for row in changed_evidence['nearestJointSource']['rows']
                                           if row['role'] == 'check')
                        exposure = changed_evidence['physicalMetalCHECK'][0]
                    else:
                        changed_row = changed_evidence['physicalMetalCHECK'][0]
                        exposure = next(row for row in changed_evidence['annotations'] if row['role'] == 'fit')
                        expected_error = 'H20 CHECK exposure holdout'
                    changed_row['sourceImage'] = copy.deepcopy(exposure['sourceImage'])
                    changed_row['timeSeconds'] = exposure['timeSeconds']
                evidence_path = root / camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE
                evidence_path.write_text(json.dumps(changed_evidence, indent=2) + '\n')
                evidence_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                changed_packet['generationDependencies'][camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE]['sha256'] = (
                    evidence_hash)
                packet_path = root / camera_tracks.SYNTHESIS_AUTOMATIC_MOTION
                packet_path.write_text(json.dumps(changed_packet, indent=2) + '\n')
                packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
                # Re-pin real fixture bytes so refusal must come from the typed
                # holdout and actual exposure sets, not the outer digest gate.
                with patch.object(camera_tracks, 'ROOT', root), \
                        patch.object(camera_tracks, 'SYNTHESIS_AUTOMATIC_MOTION_SHA256', packet_hash), \
                        patch.object(camera_tracks, 'SYNTHESIS_AUTOMATIC_EVIDENCE_SHA256', evidence_hash):
                    with self.assertRaisesRegex(ValueError, expected_error):
                        generator.synthesis_automatic_motion_packet()

    def test_current_only_source_model_and_exact_exposure_mismatches_are_refused(self):
        for mismatch in ('source', 'model', 'missing-knot-exposure', 'wrong-exposure-hash', 'off-native-clock'):
            with self.subTest(mismatch=mismatch):
                generator = self.fixture(load_motion=False)
                if mismatch == 'source':
                    generator.data['source']['sha256'] = '0' * 64
                elif mismatch == 'model':
                    generator.data['model']['sha256'] = '0' * 64
                elif mismatch == 'missing-knot-exposure':
                    generator.data['frames'] = [frame for frame in generator.data['frames']
                        if frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')) != 2557]
                else:
                    rows = [frame for frame in generator.data['frames'] if frame['shotId'] == 'rocker-bank'
                        and frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')) == 2557]
                    for frame in rows:
                        if mismatch == 'wrong-exposure-hash':
                            frame['sourceImage']['sha256Bgr8'] = '0' * 64
                        else:
                            frame['decodedTimeSeconds'] += 0.001
                with replay_source_bytes(historical_synthesis_dependencies()), self.assertRaises(ValueError):
                    generator.synthesis_automatic_motion_packet()

    def test_current_only_missing_motion_and_changed_native_math_never_fall_back_to_old_fold(self):
        generator = self.fixture(load_motion=False)
        packet = json.loads((camera_tracks.ROOT / camera_tracks.SYNTHESIS_AUTOMATIC_MOTION).read_text())
        paths = [camera_tracks.SYNTHESIS_AUTOMATIC_MOTION, *packet['generationDependencies']]
        sealed_sources = historical_synthesis_dependencies()
        changed_paths = {
            'changed-native-math': 'web/src/mechanics.ts',
            'changed-native-data': 'web/src/mechanics-data.ts',
            'changed-kinematics': 'web/src/kinematics.ts',
            'changed-motion-producer': 'web/scripts/generate-8KmVDxkia_w-automatic-motion.py',
        }
        for mismatch in ('missing-motion', 'missing-native-math', *changed_paths):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                expected_error = 'Required Synthesis automatic motion/evidence unavailable'
                if mismatch != 'missing-motion':
                    # Every other dependency starts with its exact declared bytes;
                    # refusal must identify this mutation, not unrelated live drift.
                    for relative in paths:
                        if mismatch == 'missing-native-math' and relative == 'web/src/mechanics.ts':
                            continue
                        target = root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(sealed_sources[relative] if relative in sealed_sources
                                           else (camera_tracks.ROOT / relative).read_bytes())
                    if mismatch == 'missing-native-math':
                        expected_error = 'Synthesis automatic dependency unavailable: web/src/mechanics.ts'
                    else:
                        changed_path = changed_paths[mismatch]
                        dependency = root / changed_path
                        dependency.write_bytes(dependency.read_bytes() + b'\n')
                        expected_error = f'Synthesis automatic native-math dependency differs: {changed_path}'
                with patch.object(camera_tracks, 'ROOT', root), self.assertRaisesRegex(ValueError, expected_error):
                    generator.synthesis_automatic_motion_packet()


class CamrodRendererLineageTests(unittest.TestCase):
    def test_historical_replay_does_not_approve_current_scene(self):
        generator = historical_synthesis_generator()
        current_scene = (camera_tracks.ROOT / 'web/src/scene.ts').read_bytes()
        self.assertNotEqual(hashlib.sha256(current_scene).hexdigest(), HISTORICAL_SCENE_SHA256)
        # No filesystem fixture here: the real live source seal must refuse
        # the historical GPU packet even when unrelated replay tests pass.
        with self.assertRaisesRegex(ValueError, 'source/native/code/intrinsics lineage differs'):
            generator.synthesis_coarse_framing_packet()

    def test_even_cosmetic_source_change_requires_new_gpu_evidence(self):
        generator = historical_synthesis_generator()
        with replay_source_bytes({'web/src/scene.ts': historical_scene_bytes() + b'\n'}), \
                self.assertRaisesRegex(ValueError, 'source/native/code/intrinsics lineage differs'):
            generator.synthesis_coarse_framing_packet()


if __name__ == '__main__':
    unittest.main()
