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
camera_tracks = load_script('generate-analysis-synthesis-source-tracks.py',
                            'source_generation_camera_tracks')
intro_choices = load_script('generate-intro-spin-current-choices.py',
                            'source_generation_intro_choices')




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


class NativeAnchorMotionTests(unittest.TestCase):
    def anchor(self, part):
        return {
            'id': 'native-feature',
            'partPath': f'harmonic-analyzer/paper-drive/{part}',
            'partLocalMetres': [0.001, 0.002, 0.003],
            'correspondenceEvidence': 'Explicit feature on the named native body.',
        }

    def test_latched_paper_supports_are_fixed_not_implicitly_moving(self):
        for part in ('transgear-arm-1', 'latch-hook-bracket-1',
                     'transgear-pivot-spring-1'):
            with self.subTest(part=part):
                self.assertEqual(common.anchor_motion(self.anchor(part)), 'fixed')

    def test_paper_spin_ownership_does_not_identify_a_feature_relative_to_axis(self):
        for part in ('transgear-knob-drive-pin-1', 'transgear-disc-hub-1',
                     'transgear-removable-1'):
            with self.subTest(part=part):
                self.assertIsNone(common.anchor_motion(self.anchor(part)))

    def test_native_fixed_ownership_does_not_supply_missing_source_correspondence(self):
        anchor = self.anchor('transgear-arm-1')
        del anchor['correspondenceEvidence']
        self.assertIsNone(common.anchor_motion(anchor))

    def test_removed_native_paper_support_has_no_current_fixed_ownership(self):
        self.assertIsNone(common.anchor_motion(self.anchor('transgear-stub-1')))


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


def current_source_fixture():
    data = exact_exposure()
    data['source'].update(videoId=common.VIDEO_IDS[0], durationSeconds=0.3,
                          fps={'numerator': 20, 'denominator': 1})
    data['model'] = common.current_model_identity()
    data['shots'] = [{'id': 'machine', 'startSeconds': 0, 'endSeconds': 0.3,
                     'classification': 'machine', 'hasCorrespondingMachine': True}]
    frame = data['frames'][0]
    frame.update(timeSeconds=0.05, decodedTimeSeconds=0.05, decodedFrameIndex=1)
    frame['sourceImage']['frameIndex'] = 1
    frame['views'] = [{'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080],
                      'presentation': 'native', 'camera': None}]
    data['frames'] = [frame]
    data['anchors'] = []
    return data


class CurrentObservationBoundaryTests(unittest.TestCase):
    def test_historical_only_or_current_track_cannot_fallback_for_either_loader_mode(self):
        video_id = common.VIDEO_IDS[0]
        with tempfile.TemporaryDirectory() as directory:
            historical = Path(directory) / 'content'
            current = historical / 'v39'
            current.mkdir(parents=True)
            document = current_source_fixture()
            for suffix in ('observations', 'track', 'source-track'):
                (historical / f'{video_id}.{suffix}.json').write_text(json.dumps(document))
            (current / f'{video_id}.track.json').write_text(json.dumps(document))
            before = {str(path.relative_to(historical)): path.read_bytes()
                      for path in historical.rglob('*') if path.is_file()}
            with patch.object(common, 'CURRENT_CONTENT', current), patch.object(
                    common, 'HISTORICAL_CONTENT', historical):
                for prefer_track in (False, True):
                    with self.subTest(prefer_track=prefer_track), self.assertRaises(FileNotFoundError):
                        common.load_observations(video_id, prefer_track=prefer_track)
            self.assertEqual({str(path.relative_to(historical)): path.read_bytes()
                              for path in historical.rglob('*') if path.is_file()}, before)

    def test_current_observations_win_over_historical_and_track_and_reject_old_model(self):
        video_id = common.VIDEO_IDS[0]
        with tempfile.TemporaryDirectory() as directory:
            historical = Path(directory) / 'content'
            current = historical / 'v39'
            current.mkdir(parents=True)
            document = current_source_fixture()
            decoy = copy.deepcopy(document)
            decoy['frames'][0]['landmarks'] = [{'anchorId': 'old-only-check',
                                               'role': 'check', 'pixel': [99, 100]}]
            for root, suffix in ((historical, 'observations'), (historical, 'track'),
                                 (current, 'track')):
                (root / f'{video_id}.{suffix}.json').write_text(json.dumps(decoy))
            path = current / f'{video_id}.observations.json'
            path.write_text(json.dumps(document))
            with patch.object(common, 'CURRENT_CONTENT', current), patch.object(
                    common, 'HISTORICAL_CONTENT', historical):
                for prefer_track in (False, True):
                    self.assertEqual(common.load_observations(video_id, prefer_track), document)
                document['model']['sha256'] = '0' * 64
                path.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    common.load_observations(video_id, prefer_track=True)

    def test_prepare_current_track_never_targets_historical_root_and_refuses_wrong_identity(self):
        track = current_source_fixture()
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / 'content/v39'
            with patch.object(common, 'CURRENT_CONTENT', current):
                path, serialized = common.prepare_track(track)
                self.assertEqual(path, current / f'{track["source"]["videoId"]}.source-track.json')
                self.assertEqual(json.loads(serialized), track)
                self.assertFalse(current.exists())
                for mismatch in ('model', 'video'):
                    changed = copy.deepcopy(track)
                    if mismatch == 'model':
                        changed['model']['sha256'] = '0' * 64
                    else:
                        changed['source']['videoId'] = 'not-one-of-the-six'
                    with self.subTest(mismatch=mismatch), self.assertRaises(ValueError):
                        common.prepare_track(changed)
                self.assertFalse(current.exists())


class RequiredSourceLossTests(unittest.TestCase):
    def test_full_unknown_view_null_pixel_loss_survives_ready_camera_and_input(self):
        data = current_source_fixture()
        frame = data['frames'][0]
        loss = {'anchorId': 'unknown-native-feature', 'viewId': 'unresolved-panel',
                'role': 'check', 'sourcePixels': None, 'required': True,
                'sourceImage': copy.deepcopy(frame['sourceImage']),
                'decodedTimeSeconds': frame['decodedTimeSeconds'],
                'sourceFrameIndex': 1, 'reason': 'Original source feature remains unresolved.'}
        frame['unavailable'] = [loss]
        frame['landmarks'] = [{'anchorId': 'unavailable-feature', 'viewId': 'unresolved-panel',
                               'role': 'check', 'pixel': None, 'status': 'unavailable'},
                              {'anchorId': 'unavailable-feature', 'viewId': 'main',
                               'role': 'fit', 'pixel': [12.5, 24.25], 'status': 'observed'}]
        # Forged numeric coordinates cannot overrule an explicit unavailable proof.
        data['anchors'] = [{'id': 'unavailable-feature',
                            'partPath': 'harmonic-analyzer/frame/harmonic-base-1',
                            'partLocalMetres': [1, 2, 3], 'motion': 'fixed',
                            'correspondenceEvidence': 'Forged coordinate-bearing evidence.',
                            'nativeAssociation': {'status': 'unavailable',
                                                  'reason': 'Exact native body was removed.'}}]
        camera = {'positionMetres': [0, 0, 1], 'quaternion': [0, 0, 0, 1],
                  'verticalFovDegrees': 45}
        chosen = {'crankTurns': 0, 'amplitudes': [0] * 20, 'phases': [0] * 20,
                  'gearing': 'medium-medium', 'magnification': 1,
                  'setup': {key: 0 for key in common.SETUP_FIELDS}}

        def ready_view(source_frame):
            return [{'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080],
                     'presentation': 'native', 'camera': copy.deepcopy(camera),
                     'input': copy.deepcopy(chosen)}]

        track = common.build_track(data, ready_view)
        self.assertIsNone(track['anchors'][0]['motion'])
        for row in track['frames']:
            self.assertIn(loss, row['unavailable'])
            for view_id, pixels, role in (('unresolved-panel', None, 'check'),
                                          ('main', [12.5, 24.25], 'fit')):
                mapped_loss = next(item for item in row['unavailable']
                                   if item.get('anchorId') == 'unavailable-feature'
                                   and item.get('viewId') == view_id)
                self.assertTrue(mapped_loss['required'])
                self.assertEqual(mapped_loss['sourcePixels'], pixels)
                self.assertEqual(mapped_loss['role'], role)
            self.assertEqual(row['sourceImage'], frame['sourceImage'])
            self.assertEqual(row['decodedTimeSeconds'], frame['decodedTimeSeconds'])
            self.assertEqual(row['landmarks'], [frame['landmarks'][1]])
        self.assertTrue(all(stage == {'status': 'unmeasured'} for stage in track['stages'].values()))
        self.assertTrue(any('unavailable-feature' in reason
                            for reason in track['sourceMeasurements']['blockers']))

    def test_required_sample_refuses_missing_cross_cut_or_distant_actual_pts(self):
        for missing in ('no-rows', 'null-pts', 'cross-cut', 'distant-pts'):
            with self.subTest(missing=missing):
                data = current_source_fixture()
                if missing == 'no-rows':
                    data['frames'] = []
                elif missing == 'null-pts':
                    data['frames'][0]['decodedTimeSeconds'] = None
                elif missing == 'cross-cut':
                    data['frames'][0]['decodedTimeSeconds'] = data['shots'][0]['endSeconds']
                else:
                    data['source']['durationSeconds'] = 0.9
                    data['shots'][0]['endSeconds'] = 0.9
                    data['frames'][0]['decodedTimeSeconds'] = 0.500001
                with self.assertRaises(ValueError):
                    common.selected_frames(data)

    def test_half_second_boundary_retains_real_pts_and_source_identity(self):
        data = current_source_fixture()
        data['source']['durationSeconds'] = 0.9
        data['shots'][0]['endSeconds'] = 0.9
        data['frames'][0]['decodedTimeSeconds'] = 0.5
        original = copy.deepcopy(data['frames'][0])
        selected = common.selected_frames(data)
        alias = next(row for row in selected if row['timeSeconds'] == 0)
        self.assertEqual(alias['decodedTimeSeconds'], 0.5)
        self.assertEqual(alias['retainedObservationTimeSeconds'], original['timeSeconds'])
        self.assertEqual(alias['sourceImage'], original['sourceImage'])
        self.assertEqual(alias['landmarks'], original['landmarks'])


class OperationCurrentCatalogTests(unittest.TestCase):
    def fixture(self):
        data = current_source_fixture()
        data['source']['videoId'] = 'jfH-NbsmvD4'
        anchor = {'id': 'removed-feature', 'kind': 'physical-feature',
                  'nativeAssociation': {'status': 'unavailable',
                                        'reason': 'Original native body removed.'}}
        data['anchors'] = [anchor]
        seeds = {'model': copy.deepcopy(data['model']), 'sourceSha256': data['source']['sha256']}
        catalogue = {'model': copy.deepcopy(data['model']),
                     'associations': [{'status': 'unavailable', 'anchor': copy.deepcopy(anchor)}]}
        return data, seeds, catalogue

    def test_current_catalog_refuses_lost_feature_wrong_tuple_or_forged_coordinates(self):
        for mismatch in ('missing-feature', 'duplicate-feature', 'catalogue-model',
                         'seed-model', 'source', 'qualified-unavailable', 'forged-coordinates'):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                data, seeds, catalogue = self.fixture()
                if mismatch == 'missing-feature':
                    catalogue['associations'] = []
                elif mismatch == 'duplicate-feature':
                    catalogue['associations'].append(copy.deepcopy(catalogue['associations'][0]))
                elif mismatch == 'catalogue-model':
                    catalogue['model']['sha256'] = '0' * 64
                elif mismatch == 'seed-model':
                    seeds['model']['sha256'] = '0' * 64
                elif mismatch == 'source':
                    seeds['sourceSha256'] = '0' * 64
                elif mismatch == 'qualified-unavailable':
                    data['anchors'][0]['nativeAssociation']['status'] = 'mapped'
                else:
                    data['anchors'][0].update(partPath='harmonic-analyzer/frame/plate-1',
                                              partLocalMetres=[1, 2, 3])
                root = Path(directory)
                (root / 'jfH-NbsmvD4.native-association-catalog.json').write_text(json.dumps(catalogue))
                with patch.object(rocker.common, 'CURRENT_CONTENT', root), self.assertRaises(ValueError):
                    rocker.require_current_choices(data, seeds)

    def test_orphan_landmark_is_refused_even_with_null_pixel_or_unknown_view(self):
        for pixels in ([10.5, 20.25], None):
            with self.subTest(pixels=pixels):
                data, _, _ = self.fixture()
                data['frames'][0]['landmarks'] = [{'anchorId': 'orphan-feature',
                    'viewId': 'unknown-panel', 'role': 'check', 'pixel': pixels,
                    'status': 'unavailable' if pixels is None else 'observed'}]
                with self.assertRaises(ValueError):
                    rocker.require_catalogued_landmarks(data)


class AnalysisSynthesisCurrentViewTests(unittest.TestCase):
    def test_current_choice_cannot_supply_missing_or_changed_source_clock(self):
        data = current_source_fixture()
        generator = camera_tracks.Generator.__new__(camera_tracks.Generator)
        generator.data = data
        frame = data['frames'][0]
        key = tuple(camera_tracks.choices.frame_key(frame))
        generator.by_frame = {key: {'views': []}}
        for mismatch in ('missing-key', 'shot', 'label', 'actual-pts'):
            with self.subTest(mismatch=mismatch):
                changed = copy.deepcopy(frame)
                if mismatch == 'missing-key':
                    generator.by_frame = {}
                elif mismatch == 'shot':
                    changed['shotId'] = 'different-shot'
                elif mismatch == 'label':
                    changed['timeSeconds'] += 0.001
                else:
                    changed['decodedTimeSeconds'] += 0.001
                with self.assertRaises(ValueError):
                    generator.views(changed)
                generator.by_frame = {key: {'views': []}}

    def test_current_choice_cannot_erase_or_alias_unknown_required_view_layout(self):
        data = current_source_fixture()
        generator = camera_tracks.Generator.__new__(camera_tracks.Generator)
        generator.data = data
        frame = data['frames'][0]
        key = tuple(camera_tracks.choices.frame_key(frame))
        for mismatch in ('erased', 'unknown-view', 'rect', 'mirror', 'warp', 'composite'):
            with self.subTest(mismatch=mismatch):
                source_view = copy.deepcopy(frame['views'][0])
                planned = camera_tracks.choices.layout(source_view)
                if mismatch == 'erased':
                    choices = []
                else:
                    if mismatch == 'unknown-view':
                        planned['id'] = 'unknown-panel'
                    elif mismatch == 'rect':
                        planned['rectSourcePixels'] = [0, 0, 960, 1080]
                    elif mismatch == 'mirror':
                        planned['presentation'] = 'horizontal-mirror'
                    elif mismatch == 'warp':
                        planned['imagePlaneWarp'] = {'kind': 'homography',
                            'unwarpedViewportPixels': [1920, 1080],
                            'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]}
                    else:
                        planned['composite'] = {'mode': 'opaque'}
                    choices = [{'layout': planned}]
                generator.by_frame = {key: {'views': choices}}
                with self.assertRaises(ValueError):
                    generator.views(frame)

    def test_camera_numbers_never_transfer_old_fit_status_or_native_receipts(self):
        camera = {'positionMetres': [0.1, 0.2, 1.0], 'quaternion': [0, 0, 0, 1],
                  'verticalFovDegrees': 45, 'principalPointViewportPixels': [960, 540],
                  'fitRmsPx': 0.1, 'heldOutMaxPx': 0.2, 'status': 'matched',
                  'nativeWorldReceipt': {'passed': True}, 'GPUAcceptance': True}
        expected = {key: camera[key] for key in ('positionMetres', 'quaternion',
                    'verticalFovDegrees', 'principalPointViewportPixels')}
        self.assertEqual(camera_tracks.choices.strict_camera(camera), expected)
        self.assertEqual(intro_choices.current_camera(camera), expected)
        self.assertEqual(rocker.current_camera(camera), expected)

    def test_invalid_current_camera_coordinates_refuse_instead_of_qualifying(self):
        for mismatch in ('boolean-position', 'nonfinite', 'invalid-quaternion', 'fov'):
            with self.subTest(mismatch=mismatch):
                camera = {'positionMetres': [0, 0, 1], 'quaternion': [0, 0, 0, 1],
                          'verticalFovDegrees': 45}
                if mismatch == 'boolean-position':
                    camera['positionMetres'][0] = True
                elif mismatch == 'nonfinite':
                    camera['positionMetres'][0] = float('inf')
                elif mismatch == 'invalid-quaternion':
                    camera['quaternion'][0] = 1
                else:
                    camera['verticalFovDegrees'] = 180
                with self.assertRaises(ValueError):
                    camera_tracks.choices.strict_camera(camera)


class IntroSpinCurrentInputTests(unittest.TestCase):
    def fixture(self):
        value = {'crankTurns': 0, 'amplitudes': [0] * 20, 'phases': [0] * 20,
                 'gearing': 'medium-medium', 'magnification': 1,
                 'setup': {key: 0 for key in common.SETUP_FIELDS}}
        # Explicit test parameter domain; no claimed native geometry or cache authority.
        mech = {'magnifier': {'clampRadiusBandMm': [50, 100, 200],
                              'fixtureOffsetRangeM': [-0.02, 0.02]},
                'summing': {'anchorArmMm': 100},
                'setup': {'coneDisengageRad': 0.5, 'pinionEngageCamRad': -0.5}}
        return value, mech

    def test_incomplete_extra_boolean_or_nonfinite_input_is_refused(self):
        for mismatch in ('missing-field', 'extra-field', 'extra-setup', 'short-array',
                         'boolean', 'nonfinite'):
            with self.subTest(mismatch=mismatch):
                value, mech = self.fixture()
                if mismatch == 'missing-field':
                    del value['phases']
                elif mismatch == 'extra-field':
                    value['oldNativeCertificate'] = {'passed': True}
                elif mismatch == 'extra-setup':
                    value['setup']['inventedDegreeOfFreedom'] = 0
                elif mismatch == 'short-array':
                    value['amplitudes'].pop()
                elif mismatch == 'boolean':
                    value['setup']['coneSwingRad'] = False
                else:
                    value['phases'][0] = float('nan')
                with self.assertRaises(ValueError):
                    intro_choices.chosen_input(value, mech)

    def test_current_setup_travel_boundary_cannot_be_relaxed_by_old_numeric_choice(self):
        for coordinate, limit in (('magnification', 2.0), ('wireFixtureOffsetM', 0.02),
                                  ('coneSwingRad', 0.5), ('pinionCamRad', -0.5)):
            with self.subTest(coordinate=coordinate):
                value, mech = self.fixture()
                destination = value if coordinate == 'magnification' else value['setup']
                destination[coordinate] = limit
                self.assertEqual(intro_choices.chosen_input(value, mech), value)
                destination[coordinate] += -0.000001 if coordinate == 'pinionCamRad' else 0.000001
                with self.assertRaises(ValueError):
                    intro_choices.chosen_input(value, mech)


class SpinPresentationTests(unittest.TestCase):
    def assert_seed_refused_before_observations(self, seed):
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / 'content/v39'
            current.mkdir(parents=True)
            (current / 'XPQwKRt4Y2k.source-seeds.json').write_text(
                json.dumps({'views': {'endcard-analysis': seed}}))
            # No observations exist: wrong ordering would raise FileNotFoundError.
            with patch.object(spin.common, 'CURRENT_CONTENT', current):
                with self.assertRaises(ValueError):
                    spin.build_track()

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




class RequiredSimultaneousViewTests(unittest.TestCase):
    def test_lost_source_view_blocks_coverage_until_explicit_mapping_is_declared(self):
        for source_view_id in ('original-inset', None):
            for explicit_mapping in (False, True):
                with self.subTest(source_view_id=source_view_id, explicit_mapping=explicit_mapping):
                    data = current_source_fixture()
                    frame = data['frames'][0]
                    frame['views'].append({'id': source_view_id,
                        'rectSourcePixels': [960, 0, 960, 1080], 'presentation': 'native',
                        'camera': None})
                    original_pts = frame['decodedTimeSeconds']
                    original_image = copy.deepcopy(frame['sourceImage'])

                    def render_one_view(source_frame):
                        view = {'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080],
                                'presentation': 'native',
                                'camera': {'positionMetres': [0, 0, 1],
                                           'quaternion': [0, 0, 0, 1], 'verticalFovDegrees': 45},
                                'input': {'crankTurns': 0, 'amplitudes': [0] * 20,
                                          'phases': [0] * 20, 'gearing': 'medium-medium',
                                          'magnification': 1,
                                          'setup': {key: 0 for key in common.SETUP_FIELDS}}}
                        if explicit_mapping:
                            view['sourceViewIds'] = ['main', source_view_id]
                            view['sourceViewMappingEvidence'] = 'Explicit original simultaneous panel association.'
                        return [view]

                    track = common.build_track(data, render_one_view)
                    represented = explicit_mapping and source_view_id is not None
                    self.assertEqual(track['coverage']['status'], 'complete' if represented else 'blocked')
                    for row in track['frames']:
                        self.assertEqual(row['decodedTimeSeconds'], original_pts)
                        self.assertEqual(row['sourceImage'], original_image)
                        losses = [item for item in row['unavailable']
                                  if item.get('originalViewId') == source_view_id
                                  and 'originalViewId' in item]
                        if represented:
                            self.assertEqual(losses, [])
                        else:
                            self.assertTrue(losses)
                            self.assertTrue(all(item['required'] for item in losses))
                    self.assertTrue(all(stage == {'status': 'unmeasured'}
                                        for stage in track['stages'].values()))


class RecordedSourceCensusTests(unittest.TestCase):
    def fixture(self, census_field='decodedFrameCount', index=7):
        source = {'sha256': 'a' * 64, 'width': 640, 'height': 360,
                  'fps': {'numerator': 30000, 'denominator': 1001},
                  'durationSeconds': 100, census_field: 8}
        image = {'frameIndex': index, 'sourceSha256': source['sha256'],
                 'width': 640, 'height': 360, 'pixelFormat': 'bgr8',
                 'sha256Bgr8': 'b' * 64, 'pts': index * 1001}
        return source, image, index * 1001 / 30000

    def test_both_recorded_census_schemas_admit_last_frame_but_refuse_index_equal_count(self):
        for field in ('decodedFrameCount', 'decodedNativeFrameCount'):
            with self.subTest(census_field=field):
                source, image, time = self.fixture(field)
                self.assertEqual(camera_tracks.choices.decoded_frame_count(source), 8)
                camera_tracks.choices.validate_image(image, time, source)
                # The long declared duration is not authority to invent another decode.
                _, first_missing, missing_time = self.fixture(field, index=8)
                with self.assertRaises(ValueError):
                    camera_tracks.choices.validate_image(first_missing, missing_time, source)

    def test_missing_conflicting_boolean_or_invalid_census_refuses_actual_image(self):
        for mismatch in ('missing', 'conflicting', 'boolean', 'zero', 'negative', 'float'):
            with self.subTest(mismatch=mismatch):
                source, image, time = self.fixture()
                if mismatch == 'missing':
                    del source['decodedFrameCount']
                elif mismatch == 'conflicting':
                    source['decodedNativeFrameCount'] = 9
                elif mismatch == 'boolean':
                    source, image, time = self.fixture(index=0)
                    source['decodedFrameCount'] = True
                elif mismatch == 'zero':
                    source['decodedFrameCount'] = 0
                elif mismatch == 'negative':
                    source['decodedFrameCount'] = -1
                else:
                    source['decodedFrameCount'] = 8.0
                with self.assertRaises(ValueError):
                    camera_tracks.choices.validate_image(image, time, source)

    def test_agreeing_dual_recorded_counts_still_require_exact_pts_and_image_identity(self):
        source, image, time = self.fixture()
        source['decodedNativeFrameCount'] = source['decodedFrameCount']
        self.assertEqual(camera_tracks.choices.decoded_frame_count(source), 8)
        camera_tracks.choices.validate_image(image, time, source)
        for mismatch in ('pts', 'source', 'pixels', 'dimensions', 'frame-index'):
            with self.subTest(mismatch=mismatch):
                changed = copy.deepcopy(image)
                if mismatch == 'pts':
                    changed['pts'] += 1
                elif mismatch == 'source':
                    changed['sourceSha256'] = 'c' * 64
                elif mismatch == 'pixels':
                    changed['sha256Bgr8'] = 'invalid-digest'
                elif mismatch == 'dimensions':
                    changed['width'] += 1
                else:
                    changed['frameIndex'] = True
                with self.assertRaises(ValueError):
                    camera_tracks.choices.validate_image(changed, time, source)


if __name__ == '__main__':
    unittest.main()
