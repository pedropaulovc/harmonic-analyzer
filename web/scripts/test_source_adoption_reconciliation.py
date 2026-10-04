"""Behavioral source obligations; SOURCE_ADOPTION_IMPORTER_PATH selects exact history.

Parent runs this file only after authoring. No native model cache or video is needed.
The declared layout authority fixture is source-only; camera/certificate mutation
cannot authorize a layout mutation or qualify the resulting native playback.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
IMPORTER = Path(os.environ.get('SOURCE_ADOPTION_IMPORTER_PATH', HERE / 'adopt-v39-source-observations.py')).resolve()
spec = importlib.util.spec_from_file_location('source_reconciliation_importer', IMPORTER)
adoption = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adoption)


class UnavailableNative:
    def associate_native_anchor(self, original):
        reason = 'No current feature correspondence exists in this source-only fixture.'
        anchor = {key: copy.deepcopy(original[key]) for key in ('id', 'kind', 'description') if key in original}
        anchor['nativeAssociation'] = {'status': 'unavailable', 'reason': reason, 'proof': {}}
        return {'status': 'unavailable', 'reason': reason, 'proof': {}, 'anchor': anchor}

    def associate_native_part(self, path):
        return {'status': 'unavailable', 'reason': 'Original native part is absent.', 'proof': {}}


def frame(time=0.25, views=None, *, classification='non-machine'):
    row = {'timeSeconds': time, 'decodedTimeSeconds': time, 'decodedFrameIndex': int(time * 20),
           'shotId': 'source-shot', 'classification': classification,
           'sourceImage': {'frameIndex': int(time * 20), 'sourceSha256': 'a' * 64,
                           'pixelFormat': 'bgr8', 'sha256Bgr8': 'b' * 64, 'width': 640, 'height': 360},
           'landmarks': [], 'unavailable': [], 'camera': {'oldNativeFit': True},
           'mechanicalState': {'input': {'crankTurns': 1}}}
    if views is not None:
        row['views'] = copy.deepcopy(views)
    return row


def view(ident='main', rect=None):
    return {'id': ident, 'rectSourcePixels': rect or [0, 0, 640, 360], 'presentation': 'native',
            'camera': {'oldNativeFit': True}, 'cameraFit': {'passed': True},
            'input': {'crankTurns': 1}, 'mechanicalState': {'input': {'crankTurns': 1}},
            'GPUReceipt': {'passed': True}}


def document(rows=None):
    return {'schemaVersion': 1, 'source': {'videoId': '6dW6VYXp9HM', 'sha256': 'a' * 64,
        'width': 640, 'height': 360, 'durationSeconds': 2.0, 'fps': {'numerator': 20, 'denominator': 1}},
        'model': copy.deepcopy(adoption.native.HISTORICAL_SOURCE), 'anchors': [],
        'shots': [{'id': 'source-shot', 'classification': 'non-machine', 'startSeconds': 0, 'endSeconds': 2,
                   'camera': {'oldNativeFit': True}, 'nativePose': {'passed': True}}],
        'frames': rows or [frame()], 'coverage': {'requiredEveryIntegerSecond': True}}


def approved_fixture_digest(data):
    """Independent test serialization of the public source-only authority contract."""
    records = []
    for row in data['frames']:
        layouts = []
        shot = next(shot for shot in data['shots'] if shot['id'] == row['shotId'])
        needed = (row.get('sourceMachineRequirement') == 'required' or row['classification'] == 'machine'
                  or (shot.get('hasCorrespondingMachine') is True if row['classification'] == 'non-machine'
                      else shot.get('hasCorrespondingMachine') is not False))
        defaults = [{'id': 'main', 'rectSourcePixels': [0, 0, data['source']['width'], data['source']['height']],
                     'presentation': 'native'}] if needed else []
        for original in row.get('views', defaults):
            item = {key: original[key] for key in ('id', 'rectSourcePixels', 'presentation', 'sourceViewIds',
                                                  'sourceViewMappingEvidence') if key in original}
            item.setdefault('presentation', 'native')
            if original.get('composite'):
                item['composite'] = {key: original['composite'][key] for key in ('mode', 'groupId', 'imageLayerId')
                                     if key in original['composite']}
            layouts.append(item)
        records.append({'shotId': row['shotId'], 'decodedTimeSeconds': row['decodedTimeSeconds'],
                        'classification': row['classification'], 'sourceMachineRequirement': row.get('sourceMachineRequirement'),
                        'layout': layouts})
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    records.sort(key=lambda row: (row['shotId'], row['decodedTimeSeconds'], canonical(row['layout'])))
    projection = {'source': {key: data['source'][key] for key in ('videoId', 'sha256', 'width', 'height', 'fps', 'durationSeconds')},
        'model': {key: data['model'][key] for key in ('sha256', 'sourceCommit')},
        'shots': [{key: row[key] for key in ('id', 'startSeconds', 'endSeconds', 'classification', 'hasCorrespondingMachine')
                   if key in row} for row in data['shots']], 'frames': records}
    return hashlib.sha256(canonical(projection).encode()).hexdigest()


class SourceReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def adopt(self, original, final=None, diagnostic=None, digest=None, *, declare_final_kind=True, baseline_digests=None):
        final = copy.deepcopy(final or original)
        if declare_final_kind:
            final.setdefault('kind', 'compact-source-track')
        video = original['source']['videoId']
        inputs = [('observations', original), ('source-track', final), *([('track', diagnostic)] if diagnostic else [])]
        for suffix, data in inputs:
            (self.root / f'{video}.{suffix}.json').write_text(json.dumps(data))
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        declared = {suffix: approved_fixture_digest(data) for suffix, data in inputs}
        if digest is not None:
            declared['source-track'] = digest
        declared.update(baseline_digests or {})
        authority = {video: declared}
        with patch.object(adoption, 'RECORDED_SOURCE_LAYOUT_DIGESTS', authority, create=True):
            result = adoption.adopt_video(video, UnavailableNative(), self.root)
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, before)
        return result

    def final(self, original, views):
        final = copy.deepcopy(original)
        final['kind'] = 'compact-source-track'
        final['shots'][0]['hasCorrespondingMachine'] = True
        for row in final['frames']:
            row['views'] = copy.deepcopy(views)
            row['sourceMachineRequirement'] = 'required'
        return final

    def phase_fixture(self, *, direct_reference=False):
        original = document([frame(0.25, [view()], classification='machine')])
        original['source']['durationSeconds'] = 0.5
        original['shots'][0]['endSeconds'] = 0.5
        image = original['frames'][0]['sourceImage']
        reference = copy.deepcopy(image) if direct_reference else {**image, 'frameIndex': 3, 'sha256Bgr8': 'c' * 64}
        seed = {'phaseIndex': 0, 'anchorId': 'tip', 'role': 'check', 'status': 'observed',
                'pixel': [23.0, 29.0], 'method': 'image-edge', 'uncertaintyPx': 4,
                'measurementEvidence': {'sourceImage': reference, 'contrast': 0.9}}
        original['sourceCameraRigs'] = [{'id': 'independent-source-rig', 'kind': 'source-phase-loop',
                                       'phaseCount': 1, 'measurements': [seed]}]
        phase_map = {'rigId': 'independent-source-rig', 'references': [{'phaseIndex': 0, 'sourceImage': reference}],
                     'sourceFrameMap': [{'sourceImage': image, 'referencePhaseIndex': 0,
                                         'referenceSourceImage': reference, 'ncc': 0.997,
                                         'roiSourcePixels': [0, 0, 640, 360]}]}
        path = self.root / 'sealed-source-phase-map.json'
        raw = json.dumps(phase_map, sort_keys=True).encode()
        path.write_bytes(raw)
        declaration = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                       'sourceExposureIdentityCount': 1}
        point = {'anchorId': 'tip', 'viewId': 'main', 'role': 'check', 'status': 'observed',
                 'pixel': [23.0, 29.0], 'method': 'template-match', 'uncertaintyPx': 6,
                 'measurementEvidence': {'sourceImage': image, 'referenceFrameIndex': reference['frameIndex'],
                                         'referencePixel': seed['pixel'], 'actualPatchNcc': 0.9925,
                                         'actualSearchOffsetPixels': [0, 0]}}
        original['frames'][0]['landmarks'] = [point]
        final = self.final(original, [view()])
        final['frames'][0]['timeSeconds'] = 0.20
        final['frames'][0]['landmarks'][0]['trackingEvidence'] = {
            'kind': 'retained-source-phase-patch-reacquisition', 'sourceImage': image,
            'referenceSourceImage': reference, 'referenceMeasurement': seed,
            'actualWholeMachineRoiNcc': 0.997, 'wholeMachineRoiSourcePixels': [0, 0, 640, 360],
            'actualSourcePatchNcc': 0.9925, 'actualSearchOffsetPixels': [0, 0], 'phaseMap': declaration}
        if direct_reference:
            final_point = final['frames'][0]['landmarks'][0]
            final_point['method'] = 'image-edge'
            final_point['measurementEvidence']['referenceImageEdgeMeasurement'] = copy.deepcopy(seed['measurementEvidence'])
        return original, final

    def test_sealed_source_phase_enrichment_reconciles_exact_image_alias_without_changing_check(self):
        original, final = self.phase_fixture()
        original_point = copy.deepcopy(original['frames'][0]['landmarks'][0])
        result = self.adopt(original, final)
        selected = adoption.common.selected_frames(result)
        for row in selected:
            point = row['landmarks'][0]
            for key in ('pixel', 'role', 'method', 'uncertaintyPx', 'measurementEvidence'):
                self.assertEqual(point[key], original_point[key])
            tracking = point['trackingEvidence']
            self.assertEqual(tracking['sourceImage'], row['sourceImage'])
            self.assertEqual(tracking['referenceMeasurement']['measurementEvidence']['sourceImage'],
                             tracking['referenceSourceImage'])
            self.assertEqual(tracking['actualSourcePatchNcc'], original_point['measurementEvidence']['actualPatchNcc'])
        self.assertFalse(result['nativeAdoption']['sourceAcceptance'])
        self.assertFalse(result['nativeAdoption']['GPUAcceptance'])

    def test_source_phase_normalization_never_waives_hash_reference_image_numeric_or_core_conflict(self):
        for mutation in ('sealed-hash', 'reference', 'image', 'numeric-proof', 'other-proof', 'pixel', 'role', 'method', 'uncertainty'):
            with self.subTest(mutation=mutation):
                original, final = self.phase_fixture()
                point = final['frames'][0]['landmarks'][0]
                if mutation == 'sealed-hash':
                    point['trackingEvidence']['phaseMap']['sha256'] = 'd' * 64
                elif mutation == 'reference':
                    point['measurementEvidence']['referencePixel'] = [24, 29]
                elif mutation == 'image':
                    final['frames'][0]['sourceImage'] = {**final['frames'][0]['sourceImage'], 'sha256Bgr8': 'e' * 64}
                elif mutation == 'numeric-proof':
                    point['trackingEvidence']['actualSourcePatchNcc'] = 0.999
                elif mutation == 'other-proof':
                    original['frames'][0]['landmarks'][0]['trackingEvidence'] = {
                        'kind': 'unrelated-source-proof', 'actualPatchNcc': 0.93}
                elif mutation == 'pixel':
                    point['pixel'] = [24, 29]
                elif mutation == 'role':
                    point['role'] = 'fit'
                elif mutation == 'method':
                    point['method'] = 'image-edge'
                else:
                    point['uncertaintyPx'] = 7
                with self.assertRaisesRegex(ValueError, 'phase|exact-exposure landmark'):
                    result = self.adopt(original, final)
                    adoption.common.selected_frames(result)

    def test_exact_sealed_reference_promotes_only_the_actual_independent_image_edge(self):
        original, final = self.phase_fixture(direct_reference=True)
        result = self.adopt(original, final)
        selected = adoption.common.selected_frames(result)
        seed = original['sourceCameraRigs'][0]['measurements'][0]
        for row in selected:
            point = row['landmarks'][0]
            self.assertEqual(point['method'], 'image-edge')
            self.assertEqual(point['pixel'], seed['pixel'])
            self.assertEqual(row['sourceImage'], seed['measurementEvidence']['sourceImage'])
            self.assertEqual(point['measurementEvidence']['referenceImageEdgeMeasurement'], seed['measurementEvidence'])
        self.assertFalse(result['nativeAdoption']['sourceAcceptance'])

    def test_direct_reference_promotion_preserves_method_and_existing_edge_proof_conflicts(self):
        for mutation in ('manual', 'optical-flow', 'edge-proof', 'null-edge-proof'):
            with self.subTest(mutation=mutation):
                original, final = self.phase_fixture(direct_reference=True)
                point = final['frames'][0]['landmarks'][0]
                if mutation == 'edge-proof':
                    point['measurementEvidence']['referenceImageEdgeMeasurement']['contrast'] = 0.1
                elif mutation == 'null-edge-proof':
                    point['measurementEvidence']['referenceImageEdgeMeasurement'] = None
                else:
                    point['method'] = mutation
                with self.assertRaisesRegex(ValueError, 'phase|exact-exposure landmark'):
                    result = self.adopt(original, final)
                    adoption.common.selected_frames(result)

    def test_required_later_layout_cannot_be_waived_by_equal_pts_row_order(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                original = document([frame(0.25), frame(1.25)])
                panels = [view('upper', [0, 0, 640, 180]), view('lower', [0, 180, 640, 180])]
                final = self.final(original, panels)
                diagnostic = copy.deepcopy(original)
                diagnostic['frames'] = list(reversed(diagnostic['frames'])) if reverse else diagnostic['frames']
                result = self.adopt(original, final, diagnostic)
                self.assertTrue(result['shots'][0]['hasCorrespondingMachine'])
                selected = adoption.common.selected_frames(copy.deepcopy(result))
                for row in selected:
                    self.assertTrue(adoption.common.needs_machine(row, result))
                    self.assertEqual([v['id'] for v in adoption.common.source_views(row, result)], ['upper', 'lower'])
                    self.assertEqual([v['rectSourcePixels'] for v in row['views']], [v['rectSourcePixels'] for v in panels])
                    self.assertTrue(all(v['camera'] is None and v['mechanicalState']['input'] is None for v in row['views']))
                self.assertFalse(result['nativeAdoption']['sourceAcceptance'])
                self.assertFalse(result['nativeAdoption']['GPUAcceptance'])

    def test_corrected_single_main_supersedes_competing_layers_without_aliasing_old_check(self):
        original = document([frame(0.25, [view('outgoing'), view('incoming')], classification='transition')])
        # This correction fixture is a self-contained half-second source shot;
        # its one actual quarter-second exposure covers its integer/fade census.
        original['source']['durationSeconds'] = 0.5
        original['shots'][0]['endSeconds'] = 0.5
        original['shots'][0].update(classification='transition', hasCorrespondingMachine=True)
        original['anchors'] = [{'id': 'tip', 'kind': 'feature', 'partPath': 'retired/part', 'partLocalMetres': [0, 0, 0]}]
        point = {'anchorId': 'tip', 'viewId': 'outgoing', 'role': 'check', 'status': 'observed', 'pixel': [12.5, 25.25]}
        original['frames'][0]['landmarks'] = [point]
        final = self.final(original, [view()])
        final['frames'][0]['landmarks'] = []
        result = self.adopt(original, final)
        for row in result['frames']:
            self.assertEqual([v['id'] for v in row['views']], ['main'])
            self.assertFalse(any(p.get('viewId') == 'main' for p in row['landmarks']))
            losses = [loss for loss in row['unavailable'] if loss.get('anchorId') == 'tip']
            self.assertTrue(losses)
            self.assertTrue(all(loss['required'] and loss['viewId'] == 'outgoing' and loss['sourcePixels'] == point['pixel'] for loss in losses))
        selected = adoption.common.selected_frames(copy.deepcopy(result))
        self.assertTrue(all(any(loss.get('anchorId') == 'tip' for loss in row['unavailable']) for row in selected))

    def test_unexplained_same_pts_layout_conflict_refuses_not_competing_rows(self):
        original = document([frame(0.25, [view()], classification='machine')])
        competing = copy.deepcopy(original)
        competing['frames'][0]['views'] = [view('unknown-panel', [0, 0, 320, 360])]
        with self.assertRaisesRegex(ValueError, 'layout|Layout'):
            self.adopt(original, competing, digest=approved_fixture_digest(original))

    def test_constant_shot_correction_covers_unsampled_pts_only_when_documented(self):
        original = document([frame(0.25, [view('outgoing'), view('incoming')], classification='transition'),
                             frame(0.5, [view('outgoing'), view('incoming')], classification='transition')])
        original['source']['videoId'] = '8KmVDxkia_w'
        original['shots'][0].update(id='presenter-to-spin', classification='transition', hasCorrespondingMachine=True)
        for row in original['frames']:
            row['shotId'] = 'presenter-to-spin'
        final = self.final(original, [view()])
        final['frames'] = final['frames'][:1]
        result = self.adopt(original, final)
        self.assertEqual([v['id'] for v in next(row for row in result['frames'] if row['decodedTimeSeconds'] == 0.5)['views']], ['main'])
        unknown = copy.deepcopy(original)
        unknown['shots'][0]['id'] = 'another-source-shot'
        for row in unknown['frames']:
            row['shotId'] = 'another-source-shot'
        unknown_final = self.final(unknown, [view()])
        unknown_final['frames'] = unknown_final['frames'][:1]
        unchanged = self.adopt(unknown, unknown_final)
        self.assertEqual([v['id'] for v in next(row for row in unchanged['frames'] if row['decodedTimeSeconds'] == 0.5)['views']], ['outgoing', 'incoming'])
        competing = copy.deepcopy(unknown)
        competing['frames'] = competing['frames'][1:]
        competing['frames'][0]['views'] = [view('unexplained-view')]
        with self.assertRaisesRegex(ValueError, 'layout|Layout'):
            self.adopt(unknown, unknown_final, competing)

    def test_unknown_view_and_invalid_rectangle_fail_closed_even_without_competitor(self):
        for layout in ([{'rectSourcePixels': [0, 0, 640, 360]}], [view('main', [600, 0, 640, 360])],
                       [view('main', [0, 0, -1, 360])], [view('main'), view('main')]):
            with self.subTest(layout=layout):
                with self.assertRaises(ValueError):
                    self.adopt(document([frame(0.25, layout, classification='machine')]))

    def test_final_census_kind_is_required_and_not_a_missing_kind_bypass(self):
        original = document([frame(0.25, [view()], classification='machine')])
        for kind in (None, 'observations'):
            final = copy.deepcopy(original)
            if kind is not None:
                final['kind'] = kind
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError, 'source-track|census'):
                    self.adopt(original, final, declare_final_kind=False)

    def test_unknown_preceding_layout_or_required_machine_change_is_not_explained_by_known_final(self):
        original = document([frame(0.25, [view()])])
        original['frames'][0]['sourceMachineRequirement'] = 'required'
        baseline = approved_fixture_digest(original)
        final = self.final(original, [view()])
        for change in ('layout', 'requirement'):
            altered = copy.deepcopy(original)
            if change == 'layout':
                altered['frames'][0]['views'][0]['id'] = 'unreviewed-panel'
            else:
                altered['frames'][0].pop('sourceMachineRequirement')
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, 'census|digest'):
                    self.adopt(altered, final, baseline_digests={'observations': baseline})

    def test_declared_correction_digest_rejects_unknown_layout_change_but_not_old_native_mutation(self):
        original = document([frame(0.25, [view()])])
        final = self.final(original, [view()])
        digest = approved_fixture_digest(final)
        numeric = copy.deepcopy(final)
        numeric['frames'][0]['views'][0]['camera'] = {'unsupportedChangedNativeFit': True}
        numeric['frames'][0]['views'][0]['GPUReceipt'] = {'passed': True, 'certificate': 'different-old-native'}
        numeric['frames'][0]['views'][0]['imagePlaneWarp'] = {'kind': 'homography', 'unwarpedViewportPixels': [640, 360],
            'renderToSourcePixels': [1.2, 0, 4, 0, 1.1, 5, 0, 0, 1]}
        result = self.adopt(original, numeric, digest=digest)
        for row in result['frames']:
            self.assertNotIn('imagePlaneWarp', row['views'][0])
            self.assertNotIn('GPUReceipt', row['views'][0])
            self.assertIsNone(row['views'][0]['camera'])
        changed = copy.deepcopy(final)
        changed['frames'][0]['views'][0]['rectSourcePixels'] = [0, 0, 320, 360]
        with self.assertRaisesRegex(ValueError, 'census|Census|digest'):
            self.adopt(original, changed, digest=digest)

    def test_incomplete_or_foreign_image_identity_never_authorizes_measurement_union(self):
        for missing in ('sourceSha256', 'frameIndex', 'width', 'height', 'sha256Bgr8', 'foreign-source', 'foreign-width'):
            with self.subTest(missing=missing):
                original = document([frame(0.25, [view()], classification='machine')])
                original['anchors'] = [{'id': 'first'}, {'id': 'second'}]
                first = {'anchorId': 'first', 'viewId': 'main', 'role': 'check', 'status': 'observed', 'pixel': [11.5, 22.25]}
                second = {'anchorId': 'second', 'viewId': 'main', 'role': 'check', 'status': 'observed', 'pixel': [33.5, 44.25]}
                if missing == 'foreign-source':
                    original['frames'][0]['sourceImage']['sourceSha256'] = 'd' * 64
                elif missing == 'foreign-width':
                    original['frames'][0]['sourceImage']['width'] = 320
                else:
                    original['frames'][0]['sourceImage'].pop(missing)
                original['frames'][0]['landmarks'] = [first]
                final = self.final(original, [view()])
                final['frames'][0]['landmarks'] = [second]
                result = self.adopt(original, final)
                self.assertEqual({tuple(point['anchorId'] for point in row['landmarks']) for row in result['frames']},
                                 {('first',), ('second',)})
                for row in result['frames']:
                    self.assertEqual(row['sourceImage'], original['frames'][0]['sourceImage'])
                    self.assertIn(row['landmarks'], ([first], [second]))

    def test_incompatible_contour_keeps_source_pixels_uncertainty_and_evidence_with_retired_native(self):
        original = document([frame(0.25, [view('outgoing'), view('incoming')], classification='transition')])
        original['shots'][0].update(classification='transition', hasCorrespondingMachine=True)
        contour = {'id': 'source-outline', 'role': 'check', 'sourceContourPixels': [[11.5, 12.25], [21.5, 22.25], [31.5, 32.25]],
                   'uncertaintyPx': 2.0, 'measurementEvidence': {'sourceImage': copy.deepcopy(original['frames'][0]['sourceImage']),
                                                              'method': 'Original manually observed physical silhouette'},
                   'partPath': 'retired/contour', 'nativeCandidateResidualPx': 0.1, 'cameraFit': {'passed': True}}
        original['frames'][0]['views'][0]['sourceContourChecks'] = [contour]
        final = self.final(original, [view()])
        result = self.adopt(original, final)
        for row in result['frames']:
            loss = next(loss for loss in row['unavailable'] if loss.get('contourId') == 'source-outline')
            self.assertTrue(loss['required'])
            self.assertEqual(loss['viewId'], 'outgoing')
            retained = loss['sourceObservation']
            for key in ('sourceContourPixels', 'uncertaintyPx', 'measurementEvidence'):
                self.assertEqual(retained[key], contour[key])
            self.assertEqual(retained['originalPartPath'], 'retired/contour')
            self.assertEqual(retained['nativeAssociation']['status'], 'unavailable')
            for key in ('partPath', 'nativeCandidateResidualPx', 'cameraFit'):
                self.assertNotIn(key, retained)

    def test_required_loss_machine_and_change_union_does_not_depend_on_selected_duplicate(self):
        original = document([frame(0.25, [view()])])
        original['source']['durationSeconds'] = 0.5
        original['shots'][0]['endSeconds'] = 0.5
        supplemental = copy.deepcopy(original)
        supplemental['frames'][0]['sourceMachineRequirement'] = 'required'
        loss = {'featureId': 'occluded-outline', 'viewId': 'unknown-panel', 'sourcePixels': None, 'required': True,
                'reason': 'Original unknown source panel is unresolved.'}
        supplemental['frames'][0]['unavailable'] = [loss]
        supplemental['coverage']['changeTimesSeconds'] = [0.3]
        supplemental['frames'][0]['sourceImage']['sha256Bgr8'] = 'c' * 64
        result = self.adopt(original, supplemental)
        self.assertIn(0.3, result['compactChangeTimesSeconds'])
        for row in result['frames']:
            self.assertEqual(row['sourceMachineRequirement'], 'required')
            self.assertIn(loss, row['unavailable'])
        self.assertEqual({row['sourceImage']['sha256Bgr8'] for row in result['frames']}, {'b' * 64, 'c' * 64})
        self.assertTrue(all(any(loss.get('featureId') == 'occluded-outline' for loss in row['unavailable'])
                            for row in adoption.common.selected_frames(copy.deepcopy(result))))

    def test_layout_correction_never_transplants_contours_or_pixels_between_unequal_images(self):
        original = document([frame(0.25, [view()], classification='machine')])
        original['anchors'] = [{'id': 'tip', 'kind': 'feature'}]
        point = {'anchorId': 'tip', 'viewId': 'main', 'role': 'check', 'status': 'observed', 'pixel': [11.5, 22.25]}
        original['frames'][0]['landmarks'] = [point]
        final = self.final(original, [view()])
        final['frames'][0]['sourceImage']['sha256Bgr8'] = 'c' * 64
        final['frames'][0]['landmarks'] = []
        line = {'id': 'other-exposure-contour', 'role': 'check', 'sourceLinePixels': [[4.5, 5.25], [8.5, 9.25]],
                'partPath': 'retired/part', 'partWorldLineMetres': [[0, 0, 0], [1, 0, 0]]}
        final['frames'][0]['views'][0]['sourceContourChecks'] = [line]
        result = self.adopt(original, final)
        original_row = next(row for row in result['frames'] if row['sourceImage']['sha256Bgr8'] == 'b' * 64)
        final_row = next(row for row in result['frames'] if row['sourceImage']['sha256Bgr8'] == 'c' * 64)
        self.assertEqual(original_row['landmarks'], [point])
        self.assertNotIn('sourceContourChecks', original_row['views'][0])
        self.assertEqual(final_row['landmarks'], [])
        contour = final_row['views'][0]['sourceContourChecks'][0]
        self.assertEqual(contour['sourceLinePixels'], line['sourceLinePixels'])
        self.assertEqual(contour['nativeAssociation']['status'], 'unavailable')
        self.assertNotIn('partPath', contour)

    def test_empty_required_machine_layout_remains_required_loss_not_hold_exemption(self):
        original = document([frame(0.25, [], classification='machine')])
        original['source']['durationSeconds'] = 0.5
        original['shots'][0]['endSeconds'] = 0.5
        result = self.adopt(original)
        for row in result['frames']:
            self.assertEqual(row['sourceMachineRequirement'], 'required')
            self.assertTrue(any(loss.get('viewId') is None and loss['required'] for loss in row['unavailable']))
        track = adoption.common.build_track(copy.deepcopy(result), lambda row: [])
        self.assertEqual(track['coverage']['status'], 'blocked')

    def test_source_operation_conflict_refuses_but_native_only_history_does_not_conflict(self):
        original = document([frame(0.25, [view()], classification='machine')])
        original['operations'] = [{'id': 'source-yaw', 'timeRangeSeconds': [0.2, 1.2],
                                   'states': [{'seconds': [0.4, 0.8], 'notch': '45 degree installed source yaw'}]}]
        native_only = copy.deepcopy(original)
        native_only['operations'][0]['states'][0]['cameraFit'] = {'passed': True}
        native_only['operations'][0]['GPUCertificate'] = {'passed': True}
        result = self.adopt(original, native_only)
        self.assertEqual(result['operations'][0]['states'][0]['notch'], '45 degree installed source yaw')
        self.assertFalse(result['nativeAdoption']['GPUAcceptance'])
        conflicting = copy.deepcopy(original)
        conflicting['operations'][0]['states'][0]['notch'] = 'Opposite source yaw'
        with self.assertRaisesRegex(ValueError, 'source operation'):
            self.adopt(original, conflicting)
        unknown = copy.deepcopy(original)
        unknown['operations'][0]['unreviewedSourceObservation'] = {'pixel': [12.5, 15.25]}
        with self.assertRaisesRegex(ValueError, 'cannot be dropped'):
            self.adopt(unknown)

    def test_operation_source_events_measurements_survive_nested_native_retirement(self):
        original = document([frame(0.25, [view()], classification='machine')])
        original['operations'] = [{'id': 'observed-removal-and-write', 'timeRangeSeconds': [0.1, 1.8],
            'sequence': [{'seconds': [0.2, 0.7], 'operation': 'Remove rod; simultaneous physical source views',
                          'nativePose': {'passed': True}, 'camera': {'passed': True}}],
            'states': [{'seconds': [0.8, 1.2], 'notch': 'Installed 45 degree source yaw',
                        'mechanicalState': {'input': {'crankTurns': 2}}}],
            'pairedMeasurements': [{'timeSeconds': 1.4, 'decodedTimeSeconds': 1.4, 'fixtureHeadPixel': [1.5, 2.25],
                                    'penVblockHolePixel': [500.5, 100.25], 'sourceImage': copy.deepcopy(original['frames'][0]['sourceImage']),
                                    'partPath': 'retired/pen', 'nativeAssociation': {'status': 'mapped', 'proof': {'passed': True}},
                                    'cameraFit': {'passed': True}, 'fitRmsPx': 0.1, 'GPUReceipt': {'passed': True},
                                    'nativeFrame': 28}],
            'viewRectsSourcePixels': {'fixture': [0, 0, 320, 360], 'pen': [320, 0, 320, 360]},
            'sourceTemplateCorrelation': {'fixture': 0.97, 'pen': 0.98},
            'replayMovementEnvelope': {'firstDepartureOver2PxSeconds': 0.5, 'initialPixel': [15.5, 20.25]},
            'nativePartPaths': ['retired/pen'], 'nativeScaleMm': {'pitch': 14.2}, 'input': {'crankTurns': 3}}]
        original['operations'][0]['pairedMeasurements'][0]['sourceImage']['frameIndex'] = 28
        result = self.adopt(original)
        current = result['operations'][0]
        self.assertEqual(current['sequence'][0]['seconds'], [0.2, 0.7])
        self.assertEqual(current['sequence'][0]['operation'], original['operations'][0]['sequence'][0]['operation'])
        self.assertEqual(current['states'][0]['notch'], 'Installed 45 degree source yaw')
        for key in ('viewRectsSourcePixels', 'sourceTemplateCorrelation', 'replayMovementEnvelope'):
            self.assertEqual(current[key], original['operations'][0][key])
        pair = current['pairedMeasurements'][0]
        for key in ('timeSeconds', 'decodedTimeSeconds', 'nativeFrame', 'fixtureHeadPixel', 'penVblockHolePixel', 'sourceImage'):
            self.assertEqual(pair[key], original['operations'][0]['pairedMeasurements'][0][key])
        self.assertEqual(pair['nativeAssociation']['status'], 'unavailable')
        self.assertEqual(pair['originalPartPath'], 'retired/pen')
        self.assertNotIn('partPath', pair)
        self.assertNotIn('fitRmsPx', pair)
        for context in (current, current['sequence'][0], current['states'][0], pair):
            for key in ('nativePose', 'camera', 'cameraFit', 'mechanicalState', 'GPUReceipt', 'input', 'nativePartPaths', 'nativeScaleMm'):
                self.assertNotIn(key, context)
        self.assertTrue({0.1, 0.2, 0.7, 0.8, 1.2, 1.4, 1.8} <= set(result['compactChangeTimesSeconds']))
        self.assertFalse(result['nativeAdoption']['sourceAcceptance'])


if __name__ == '__main__':
    unittest.main()
