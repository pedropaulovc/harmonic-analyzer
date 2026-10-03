"""Cache-independent raw-GLB association and original-source adoption boundaries."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load_script('native-source-association.py', 'test_raw_native_association')
adoption = load_script('adopt-v39-source-observations.py', 'test_source_adoption')
PART_PATH = 'harmonic-analyzer/frame/plate-1'


def triangle_fixture(*, index_component_type=5123, color_component_type=5126):
    """Two complete indexed primitives, including non-position typed attributes."""
    document = {
        'asset': {'version': '2.0'}, 'scene': 0,
        'scenes': [{'nodes': [0]}],
        'nodes': [{'name': 'harmonic-analyzer', 'children': [1]},
                  {'name': 'frame', 'children': [2]},
                  {'name': 'plate-1', 'mesh': 0}],
        'meshes': [{'primitives': []}],
        'materials': [{'pbrMetallicRoughness': {
            'baseColorFactor': [0.8, 0.7, 0.6, 1.0],
            'metallicFactor': 0.0, 'roughnessFactor': 0.5}}],
        'buffers': [], 'bufferViews': [], 'accessors': [],
    }
    binary = bytearray()
    formats = {5121: 'B', 5123: 'H', 5125: 'I', 5126: 'f'}

    def accessor(values, component_type, shape, *, normalized=False):
        binary.extend(b'\0' * (-len(binary) % 4))
        flattened = [component for row in values for component in row]
        storage = struct.pack('<' + formats[component_type] * len(flattened), *flattened)
        view_index = len(document['bufferViews'])
        document['bufferViews'].append({
            'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(storage)})
        binary.extend(storage)
        index = len(document['accessors'])
        document['accessors'].append({
            'bufferView': view_index, 'componentType': component_type,
            'count': len(values), 'type': shape, 'normalized': normalized})
        return index

    for height in (0.0, 2.0):
        color_scale = 255 if color_component_type == 5121 else 1.0
        attributes = {
            'POSITION': accessor([(0.0, 0.0, height), (1.0, 0.0, height),
                                  (0.0, 1.0, height)], 5126, 'VEC3'),
            'NORMAL': accessor([(0.0, 0.0, 1.0)] * 3, 5126, 'VEC3'),
            'TEXCOORD_0': accessor([(0.0, 0.0), (1.0, 0.0),
                                    (0.0, 1.0)], 5126, 'VEC2'),
            'COLOR_0': accessor([(color_scale, 0, 0, color_scale)] * 3,
                                color_component_type, 'VEC4',
                                normalized=color_component_type != 5126),
        }
        document['accessors'][attributes['POSITION']].update(
            min=[0.0, 0.0, height], max=[1.0, 1.0, height])
        indices = accessor([(0,), (1,), (2,)], index_component_type, 'SCALAR')
        document['meshes'][0]['primitives'].append({
            'mode': 4, 'attributes': attributes, 'indices': indices, 'material': 0})
    document['buffers'] = [{'byteLength': len(binary)}]
    return document, binary


def glb_bytes(document, binary):
    json_chunk = json.dumps(document, separators=(',', ':'), allow_nan=False).encode()
    json_chunk += b' ' * (-len(json_chunk) % 4)
    binary_chunk = bytes(binary) + b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    return (struct.pack('<III', 0x46546C67, 2, total)
            + struct.pack('<II', len(json_chunk), 0x4E4F534A) + json_chunk
            + struct.pack('<II', len(binary_chunk), 0x004E4942) + binary_chunk)


def original_anchor(anchor_id='plate-feature', part_path=PART_PATH):
    return {'id': anchor_id, 'kind': 'physical-feature',
            'description': 'Identified triangle feature on the authored plate.',
            'partPath': part_path, 'partLocalMetres': [0.25, 0.25, 0.0],
            'correspondenceEvidence': 'Original source identified this plate feature.',
            'cameraFit': {'status': 'passed', 'fitRmsPx': 0.0},
            'nativePoseReceipt': {'status': 'passed'},
            'GPUAcceptance': True}


class SyntheticNativeFiles(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model_serial = 0

    def model(self, fixture):
        self.model_serial += 1
        path = self.root / f'native-{self.model_serial}.glb'
        data = glb_bytes(*fixture)
        path.write_bytes(data)
        return native.RawNativeModel(path, hashlib.sha256(data).hexdigest())

    def association(self, old=None, new=None):
        return native.NativeAssociation(self.model(old or triangle_fixture()),
                                        self.model(new or triangle_fixture()))

    def assert_unavailable(self, result, original):
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['anchor']['nativeAssociation']['status'], 'unavailable')
        for key in ('id', 'kind', 'description'):
            self.assertEqual(result['anchor'][key], original[key])
        for key in ('partPath', 'partLocalMetres', 'worldMetres',
                    'correspondenceEvidence', 'cameraFit', 'nativePoseReceipt',
                    'GPUAcceptance'):
            self.assertNotIn(key, result['anchor'])
        self.assertIsInstance(result['reason'], str)
        self.assertTrue(result['reason'].strip())


class RawNativeAssociationTests(SyntheticNativeFiles):
    def test_complete_authenticated_primitives_map_with_actual_model_hashes(self):
        association = self.association()
        anchor = original_anchor()
        original = copy.deepcopy(anchor)
        result = association.associate_native_anchor(anchor)
        self.assertEqual(result['status'], 'mapped')
        self.assertEqual(result['anchor']['partPath'], PART_PATH)
        self.assertEqual(result['anchor']['partLocalMetres'], [0.25, 0.25, 0.0])
        self.assertEqual(result['proof']['currentRestWorldMetres'], [0.25, 0.25, 0.0])
        for key, model in (('historicalSource', association.old),
                           ('currentSource', association.new)):
            actual = hashlib.sha256(model.path.read_bytes()).hexdigest()
            self.assertEqual(result['proof'][key]['sha256'], actual)
            self.assertNotEqual(actual, native.HISTORICAL_SOURCE['sha256'])
            self.assertNotEqual(actual, native.APPROVED_SOURCE['sha256'])
        for key in ('cameraFit', 'nativePoseReceipt', 'GPUAcceptance'):
            self.assertNotIn(key, result['anchor'])
        self.assertEqual(anchor, original)

    def test_any_primitive_attribute_index_or_material_difference_refuses(self):
        for change in ('position', 'normal', 'uv', 'color', 'attribute-removed',
                       'attribute-added', 'index-winding', 'index-type',
                       'color-type', 'material'):
            with self.subTest(change=change):
                if change == 'index-type':
                    fixture = triangle_fixture(index_component_type=5125)
                elif change == 'color-type':
                    # Equal effective colour is still different authored typed storage.
                    fixture = triangle_fixture(color_component_type=5121)
                else:
                    fixture = triangle_fixture()
                document, binary = fixture
                # Changing only the SECOND primitive catches aggregate/first-draw aliases.
                primitive = document['meshes'][0]['primitives'][1]
                semantic = {'position': 'POSITION', 'normal': 'NORMAL',
                            'uv': 'TEXCOORD_0', 'color': 'COLOR_0'}.get(change)
                if semantic:
                    entry = document['accessors'][primitive['attributes'][semantic]]
                    offset = document['bufferViews'][entry['bufferView']]['byteOffset']
                    if semantic == 'NORMAL':
                        struct.pack_into('<fff', binary, offset, 0.0, 1.0, 0.0)
                    else:
                        struct.pack_into('<f', binary, offset, 0.5)
                elif change == 'attribute-removed':
                    del primitive['attributes']['COLOR_0']
                elif change == 'attribute-added':
                    primitive['attributes']['_FEATURE_COLOR'] = primitive['attributes']['COLOR_0']
                elif change == 'index-winding':
                    entry = document['accessors'][primitive['indices']]
                    offset = document['bufferViews'][entry['bufferView']]['byteOffset']
                    struct.pack_into('<HHH', binary, offset, 0, 2, 1)
                elif change == 'material':
                    material = copy.deepcopy(document['materials'][0])
                    material['pbrMetallicRoughness']['roughnessFactor'] = 0.75
                    document['materials'].append(material)
                    primitive['material'] = 1
                anchor = original_anchor()
                self.assert_unavailable(
                    self.association(new=fixture).associate_native_anchor(anchor), anchor)

    def test_incomplete_or_invalid_indexed_triangle_has_no_native_feature(self):
        for change in ('position', 'normal', 'indices', 'index-out-of-bounds'):
            with self.subTest(change=change):
                document, binary = triangle_fixture()
                primitive = document['meshes'][0]['primitives'][0]
                if change in ('position', 'normal'):
                    del primitive['attributes'][change.upper()]
                elif change == 'indices':
                    del primitive['indices']
                else:
                    entry = document['accessors'][primitive['indices']]
                    offset = document['bufferViews'][entry['bufferView']]['byteOffset']
                    struct.pack_into('<HHH', binary, offset, 0, 1, 3)
                anchor = original_anchor()
                self.assert_unavailable(self.association(new=(document, binary))
                                        .associate_native_anchor(anchor), anchor)

    def test_removed_qualified_path_cannot_alias_same_leaf_or_identical_replacement(self):
        document, binary = triangle_fixture()
        document['nodes'][1]['name'] = 'replacement-frame'
        document['nodes'].append({'name': 'plate-2', 'mesh': 0})
        document['nodes'][1]['children'].append(3)
        association = self.association(new=(document, binary))
        self.assertIn('harmonic-analyzer/replacement-frame/plate-1', association.new.parts)
        self.assertIn('harmonic-analyzer/replacement-frame/plate-2', association.new.parts)
        anchor = original_anchor()
        self.assert_unavailable(association.associate_native_anchor(anchor), anchor)

    def test_old_world_localizes_old_hierarchy_then_transports_new_hierarchy(self):
        old_document, old_binary = triangle_fixture()
        old_document['nodes'][0]['translation'] = [10.0, 20.0, 30.0]
        old_document['nodes'][1]['scale'] = [2.0, 3.0, 4.0]
        old_document['nodes'][2]['translation'] = [1.0, 2.0, 3.0]
        new_document, new_binary = triangle_fixture()
        new_document['nodes'][0]['translation'] = [-5.0, 7.0, 2.0]
        new_document['nodes'][1]['matrix'] = [
            0.0, 1.0, 0.0, 0.0, -2.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        new_document['nodes'][2]['translation'] = [1.0, 2.0, 3.0]
        association = self.association(old=(old_document, old_binary),
                                       new=(new_document, new_binary))
        anchor = original_anchor()
        del anchor['partLocalMetres']
        anchor['worldMetres'] = [12.5, 27.5, 42.0]
        result = association.associate_native_anchor(anchor)
        self.assertEqual(result['status'], 'mapped')
        for actual, expected in zip(result['anchor']['partLocalMetres'], [0.25, 0.5, 0.0]):
            self.assertAlmostEqual(actual, expected, places=12)
        for actual, expected in zip(result['proof']['currentRestWorldMetres'], [-10.0, 8.25, 11.0]):
            self.assertAlmostEqual(actual, expected, places=12)
        self.assertNotEqual(result['proof']['currentRestWorldMetres'], anchor['worldMetres'])
        self.assertNotIn('worldMetres', result['anchor'])

    def test_duplicate_qualified_path_is_rejected_by_actual_decoder(self):
        document, binary = triangle_fixture()
        document['nodes'].append(copy.deepcopy(document['nodes'][2]))
        document['nodes'][1]['children'].append(3)
        with self.assertRaises(ValueError):
            self.model((document, binary))

    def test_wrong_raw_hash_and_incomplete_glb_are_refused(self):
        data = glb_bytes(*triangle_fixture())
        path = self.root / 'untrusted.glb'
        path.write_bytes(data)
        with self.assertRaises(ValueError):
            native.RawNativeModel(path, '0' * 64)
        truncated = data[:-1]
        path.write_bytes(truncated)
        with self.assertRaises(ValueError):
            native.RawNativeModel(path, hashlib.sha256(truncated).hexdigest())


def historical_document(video_id):
    old_camera = {'positionMetres': [1.0, 2.0, 3.0], 'quaternion': [0, 0, 0, 1],
                  'verticalFovDegrees': 45, 'fitRmsPx': 0.1, 'status': 'matched'}
    image = {'frameIndex': 1, 'sourceSha256': 'a' * 64,
             'pixelFormat': 'bgr8', 'sha256Bgr8': 'b' * 64, 'width': 640, 'height': 360}
    frame = {
        'timeSeconds': 0.05, 'decodedTimeSeconds': 0.05, 'decodedFrameIndex': 1,
        'sourceFrameIndex': 1, 'nativeFrame': 1, 'shotId': 'machine',
        'classification': 'machine', 'sourceMachineRequirement': 'required',
        'sourceImage': image, 'camera': old_camera,
        'mechanicalState': {'input': {'crankTurns': 1}},
        'nativePoseReceipt': {'passed': True}, 'cameraFit': {'passed': True},
        'GPUReceipt': {'passed': True},
        'landmarks': [
            {'anchorId': 'plate-feature', 'viewId': 'main', 'status': 'observed',
             'role': 'fit', 'pixel': [12.5, 24.25], 'uncertaintyPx': 0.5,
             'measurementEvidence': {'sourceImage': copy.deepcopy(image)}},
            {'anchorId': 'removed-feature', 'viewId': 'main', 'status': 'observed',
             'role': 'check', 'pixel': [100.5, 80.25], 'uncertaintyPx': 1.0},
            {'anchorId': 'unidentified-feature', 'viewId': 'unknown-panel',
             'status': 'unavailable', 'role': 'check', 'pixel': None}],
        'unavailable': [{'anchorId': 'original-occluded', 'viewId': 'unknown-panel',
                         'role': 'check', 'sourcePixels': None, 'required': True,
                         'sourceImage': copy.deepcopy(image), 'decodedTimeSeconds': 0.05,
                         'reason': 'Original feature is occluded.'}],
        'sourceFeatureUnavailable': [{'anchorId': 'unresolved-outline',
                                      'viewId': 'unknown-panel', 'sourcePixels': None,
                                      'reason': 'Original panel boundary unresolved.'}],
        'sourceMeasurements': {'observedFeaturePixels': {'tip': [5, 6]},
                               'unresolvedInputFields': ['crankTurns'],
                               'nativeFitReceipt': {'passed': True}},
        'views': [{'id': 'main', 'rectSourcePixels': [0, 0, 640, 360],
                   'presentation': 'horizontal-mirror',
                   'imagePlaneWarp': {'kind': 'homography',
                       'unwarpedViewportPixels': [640, 360],
                       'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]},
                   'composite': {'mode': 'opaque'}, 'sourceViewIds': ['original-main'],
                   'sourceViewMappingEvidence': 'Original full-frame source panel.',
                   'camera': copy.deepcopy(old_camera), 'cameraFit': {'passed': True},
                   'nativePoseReceipt': {'passed': True},
                   'mechanicalState': {'input': {'crankTurns': 1}}}],
    }
    return {'schemaVersion': 1,
            'source': {'videoId': video_id, 'sha256': 'a' * 64, 'width': 640,
                       'height': 360, 'durationSeconds': 0.3,
                       'fps': {'numerator': 20, 'denominator': 1}},
            'model': copy.deepcopy(native.HISTORICAL_SOURCE),
            'anchors': [original_anchor(), original_anchor(
                'removed-feature', 'harmonic-analyzer/frame/removed-1')],
            'shots': [{'id': 'machine', 'classification': 'machine',
                       'startSeconds': 0, 'endSeconds': 0.3,
                       'hasCorrespondingMachine': True, 'camera': copy.deepcopy(old_camera),
                       'nativePose': {'passed': True}, 'cameraFit': {'passed': True},
                       'cameraEvidence': 'Old native fitted camera receipt.',
                       'mechanicalState': {'input': {'crankTurns': 1}}}],
            'frames': [frame], 'coverage': {'requiredEveryIntegerSecond': True}}


class SourceAdoptionBoundaryTests(SyntheticNativeFiles):
    def write_historical(self, document, supplement=None):
        root = self.root / 'historical'
        root.mkdir(exist_ok=True)
        video_id = document['source']['videoId']
        for suffix, data in (('observations', document),
                             ('source-track', supplement or document)):
            (root / f'{video_id}.{suffix}.json').write_text(json.dumps(data))
        return root

    def test_adoption_retains_source_exposure_roles_pixels_layout_without_old_receipts(self):
        video_id = adoption.common.VIDEO_IDS[0]
        document = historical_document(video_id)
        historical_root = self.write_historical(document)
        before = {path.name: path.read_bytes() for path in historical_root.iterdir()}
        result = adoption.adopt_video(video_id, self.association(), historical_root)
        self.assertEqual(result['source'], document['source'])
        frame, original = result['frames'][0], document['frames'][0]
        for key in ('timeSeconds', 'decodedTimeSeconds', 'decodedFrameIndex',
                    'sourceFrameIndex', 'nativeFrame', 'sourceImage', 'landmarks'):
            self.assertEqual(frame[key], original[key])
        for key in ('id', 'rectSourcePixels', 'presentation', 'imagePlaneWarp',
                    'composite', 'sourceViewIds', 'sourceViewMappingEvidence'):
            self.assertEqual(frame['views'][0][key], original['views'][0][key])
        for context in (frame, frame['views'][0]):
            self.assertIsNone(context['camera'])
            self.assertIsNone(context['mechanicalState']['input'])
            for key in ('cameraFit', 'nativePoseReceipt', 'GPUReceipt'):
                self.assertNotIn(key, context)
        for key in ('camera', 'cameraFit', 'cameraEvidence', 'nativePose', 'mechanicalState'):
            self.assertNotIn(key, result['shots'][0])
        self.assertNotIn('nativeFitReceipt', frame['sourceMeasurements'])
        self.assertFalse(result['nativeAdoption']['sourceAcceptance'])
        self.assertFalse(result['nativeAdoption']['GPUAcceptance'])
        self.assertTrue(all(stage == {'status': 'unmeasured'} for stage in result['stages'].values()))
        self.assertEqual({path.name: path.read_bytes() for path in historical_root.iterdir()}, before)

    def test_missing_native_anchors_keep_required_losses_including_null_unknown_view(self):
        document = historical_document(adoption.common.VIDEO_IDS[0])
        result = adoption.adopt_video(document['source']['videoId'], self.association(),
                                      self.write_historical(document))
        frame = result['frames'][0]
        self.assertIn(document['frames'][0]['unavailable'][0], frame['unavailable'])
        for anchor_id, view_id, pixels, role in (
                ('removed-feature', 'main', [100.5, 80.25], 'check'),
                ('unidentified-feature', 'unknown-panel', None, 'check')):
            losses = [row for row in frame['unavailable']
                      if row.get('anchorId') == anchor_id and row.get('viewId') == view_id]
            self.assertTrue(losses)
            for loss in losses:
                self.assertEqual(loss['sourcePixels'], pixels)
                self.assertEqual(loss['role'], role)
                self.assertTrue(loss['required'])
        outline = next(row for row in frame['unavailable']
                       if row.get('anchorId') == 'unresolved-outline')
        self.assertTrue(outline['required'])
        self.assertIsNone(outline['sourcePixels'])
        anchor = next(row for row in result['anchors'] if row['id'] == 'removed-feature')
        self.assertEqual(anchor['nativeAssociation']['status'], 'unavailable')
        for key in ('partPath', 'partLocalMetres', 'worldMetres', 'correspondenceEvidence'):
            self.assertNotIn(key, anchor)

    def test_supplemental_union_requires_exact_pts_hash_and_layout(self):
        for mismatch in (None, 'pts', 'hash', 'layout'):
            with self.subTest(mismatch=mismatch):
                original = historical_document(adoption.common.VIDEO_IDS[0])['frames'][0]
                original['landmarks'] = original['landmarks'][:1]
                supplement = copy.deepcopy(original)
                supplement['landmarks'] = [{'anchorId': 'supplemental-check',
                    'viewId': 'main', 'role': 'check', 'status': 'observed', 'pixel': [80.5, 12.25]}]
                if mismatch == 'pts':
                    supplement['decodedTimeSeconds'] += 0.00001
                elif mismatch == 'hash':
                    supplement['sourceImage']['sha256Bgr8'] = 'c' * 64
                elif mismatch == 'layout':
                    supplement['views'][0]['rectSourcePixels'] = [0, 0, 320, 360]
                frames = [adoption.source_frame(original)]
                adoption.retain_supplemental_frames(frames, [supplement])
                if mismatch is None:
                    self.assertEqual(frames[0]['landmarks'],
                                     original['landmarks'] + supplement['landmarks'])
                else:
                    retained = next(row for row in frames
                                    if row['landmarks'] == original['landmarks'])
                    self.assertEqual(retained['decodedTimeSeconds'], original['decodedTimeSeconds'])
                    self.assertEqual(retained['sourceImage'], original['sourceImage'])
                    supplemental = next(row for row in frames
                                        if row['landmarks'] == supplement['landmarks'])
                    self.assertEqual(supplemental['decodedTimeSeconds'], supplement['decodedTimeSeconds'])
                    self.assertEqual(supplemental['sourceImage'], supplement['sourceImage'])
                    self.assertEqual(supplemental['views'][0]['rectSourcePixels'],
                                     supplement['views'][0]['rectSourcePixels'])

    def test_supplement_without_actual_pts_refuses_instead_of_borrowing(self):
        frame = historical_document(adoption.common.VIDEO_IDS[0])['frames'][0]
        frame['decodedTimeSeconds'] = None
        with self.assertRaises(ValueError):
            adoption.retain_supplemental_frames([], [frame])

    def test_historical_model_video_and_source_mismatch_refuse_adoption(self):
        video_id = adoption.common.VIDEO_IDS[0]
        for mismatch in ('model', 'video', 'source'):
            with self.subTest(mismatch=mismatch):
                document = historical_document(video_id)
                supplement = copy.deepcopy(document)
                if mismatch == 'model':
                    supplement['model']['sha256'] = '0' * 64
                elif mismatch == 'video':
                    supplement['source']['videoId'] = adoption.common.VIDEO_IDS[1]
                else:
                    supplement['source']['sha256'] = 'c' * 64
                root = self.write_historical(document, supplement)
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with self.assertRaises(ValueError):
                    adoption.adopt_video(video_id, self.association(), root)
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_body_lines_keep_exact_source_pixels_but_not_old_world_or_bias_authority(self):
        for boundary in ('mapped', 'removed', 'changed'):
            with self.subTest(boundary=boundary):
                document = historical_document(adoption.common.VIDEO_IDS[0])
                original = document['frames'][0]
                path = 'harmonic-analyzer/frame/removed-1' if boundary == 'removed' else PART_PATH
                line = {'id': 'source-contour', 'partPath': path, 'role': 'check',
                        'sourceLinePixels': [[20.5, 30.25], [80.5, 90.25]],
                        'partWorldLineMetres': [[12.5, 27.5, 42.0], [13.0, 27.5, 42.0]],
                        'nativeCandidateResidualPx': 0.1,
                        'measurementEvidence': {'sourceImage': copy.deepcopy(original['sourceImage']),
                            'axisPerspectiveBiasBoundPx': 0.25,
                            'axisPerspectiveEvidence': 'Historical native frame only.'}}
                original['sourceContourChecks'] = [line]
                secondary = copy.deepcopy(line)
                secondary['id'] = 'source-line-check'
                original['views'][0]['nativeLineChecks'] = [secondary]
                old_document, old_binary = triangle_fixture()
                old_document['nodes'][0]['translation'] = [10.0, 20.0, 30.0]
                old_document['nodes'][1]['scale'] = [2.0, 3.0, 4.0]
                old_document['nodes'][2]['translation'] = [1.0, 2.0, 3.0]
                new_document, new_binary = triangle_fixture()
                if boundary == 'changed':
                    new_document['materials'][0]['pbrMetallicRoughness']['roughnessFactor'] = 0.75
                association = self.association(old=(old_document, old_binary),
                                               new=(new_document, new_binary))
                result = adoption.adopt_video(document['source']['videoId'], association,
                                              self.write_historical(document))
                frame = result['frames'][0]
                current = frame['sourceContourChecks'][0]
                self.assertEqual(set(result['nativeBodyAssociations']), {path})
                body = result['nativeBodyAssociations'][path]
                serialized = body['serializedProof']
                self.assertEqual(json.loads(serialized),
                                 {key: body[key] for key in ('status', 'reason', 'proof')})
                self.assertEqual(body['proof']['historicalSource']['sha256'], association.old.sha256)
                self.assertEqual(body['proof']['currentSource']['sha256'], association.new.sha256)
                reference_digest = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
                for record in (current, frame['views'][0]['nativeLineChecks'][0]):
                    reference = record['nativeAssociation']
                    self.assertEqual(reference['proofRef'], path)
                    self.assertEqual(reference['proofSha256'], reference_digest)
                    self.assertNotIn('proof', reference)
                self.assertEqual(current['sourceLinePixels'], line['sourceLinePixels'])
                self.assertEqual(current['measurementEvidence']['sourceImage'],
                                 line['measurementEvidence']['sourceImage'])
                self.assertNotIn('nativeCandidateResidualPx', current)
                self.assertNotIn('axisPerspectiveBiasBoundPx', current['measurementEvidence'])
                self.assertNotIn('axisPerspectiveEvidence', current['measurementEvidence'])
                self.assertEqual(current['historicalNativeEvidence']['model'], native.HISTORICAL_SOURCE)
                self.assertNotIn('partWorldLineMetres', current)
                if boundary != 'mapped':
                    self.assertEqual(current['nativeAssociation']['status'], 'unavailable')
                    self.assertNotIn('partPath', current)
                    self.assertNotIn('partLocalLineMetres', current)
                    loss = next(row for row in frame['unavailable']
                                if row.get('contourId') == 'source-contour')
                    self.assertTrue(loss['required'])
                    self.assertEqual(loss['role'], 'check')
                else:
                    self.assertEqual(current['nativeAssociation']['status'], 'mapped')
                    self.assertEqual(current['partPath'], PART_PATH)
                    for actual, expected in zip(current['partLocalLineMetres'],
                                                ([0.25, 0.5, 0.0], [0.5, 0.5, 0.0])):
                        for component, wanted in zip(actual, expected):
                            self.assertAlmostEqual(component, wanted, places=12)

    def test_unidentified_top_level_tracking_loss_reaches_current_consumer_with_null_view(self):
        document = historical_document(adoption.common.VIDEO_IDS[0])
        original = document['frames'][0]
        loss = {'featureId': 'raised-brass-tip', 'shotId': original['shotId'],
                'decodedTimeSeconds': original['decodedTimeSeconds'],
                'role': 'check', 'pixel': None,
                'sourceImage': copy.deepcopy(original['sourceImage']),
                'reason': 'Original unidentified source feature tracking was lost.'}
        document['trackingLosses'] = [loss]
        result = adoption.adopt_video(document['source']['videoId'], self.association(),
                                      self.write_historical(document))
        self.assertEqual(result['trackingLosses'], [loss])
        track = adoption.common.build_track(result, lambda frame: [])
        for frame in track['frames']:
            ledger = next(row for row in frame['unavailable']
                          if row.get('featureId') == 'raised-brass-tip')
            self.assertTrue(ledger['required'])
            self.assertIsNone(ledger['viewId'])
            self.assertIsNone(ledger['originalViewId'])
            self.assertIsNone(ledger['sourcePixels'])
            self.assertEqual(ledger['role'], 'check')
            self.assertEqual(ledger['decodedTimeSeconds'], original['decodedTimeSeconds'])
            self.assertEqual(ledger['sourceImage'], original['sourceImage'])

    def test_dense_diagnostic_exposures_and_losses_are_retained_without_promoting_all_change_keys(self):
        video_id = adoption.common.VIDEO_IDS[0]
        document = historical_document(video_id)
        document['compactChangeTimesSeconds'] = [0.1]
        document['coverage']['changeTimesSeconds'] = [0.15]

        def exposure(index):
            frame = copy.deepcopy(document['frames'][0])
            frame.update(timeSeconds=index / 20, decodedTimeSeconds=index / 20,
                         decodedFrameIndex=index, sourceFrameIndex=index, nativeFrame=index)
            frame['sourceImage']['frameIndex'] = index
            for point in frame['landmarks']:
                if 'measurementEvidence' in point:
                    point['measurementEvidence']['sourceImage'] = copy.deepcopy(frame['sourceImage'])
            for loss in frame['unavailable']:
                loss['decodedTimeSeconds'] = frame['decodedTimeSeconds']
                loss['sourceImage'] = copy.deepcopy(frame['sourceImage'])
            return frame

        compact = copy.deepcopy(document)
        compact['kind'] = 'compact-source-track'
        compact['frames'] = [exposure(5)]
        diagnostic = copy.deepcopy(document)
        diagnostic['kind'] = 'dense-diagnostic-source-track'
        diagnostic['frames'] = [exposure(index) for index in (2, 3, 4)]
        diagnostic_loss = {'featureId': 'diagnostic-unidentified-feature', 'viewId': None,
                           'role': 'check', 'sourcePixels': None, 'required': True,
                           'decodedTimeSeconds': 0.2,
                           'sourceImage': copy.deepcopy(diagnostic['frames'][-1]['sourceImage']),
                           'reason': 'Original dense-exposure source feature unresolved.'}
        diagnostic['frames'][-1]['unavailable'].append(diagnostic_loss)
        root = self.write_historical(document, compact)
        (root / f'{video_id}.track.json').write_text(json.dumps(diagnostic))
        before = {path.name: path.read_bytes() for path in root.iterdir()}
        result = adoption.adopt_video(video_id, self.association(), root)
        self.assertEqual(result['compactChangeTimesSeconds'], [0.1, 0.15, 0.25])
        for original in [*document['frames'], *diagnostic['frames'], *compact['frames']]:
            retained = next(frame for frame in result['frames']
                            if frame['decodedTimeSeconds'] == original['decodedTimeSeconds'])
            self.assertEqual(retained['sourceImage'], original['sourceImage'])
            self.assertEqual(retained['landmarks'], original['landmarks'])
            for loss in original['unavailable']:
                self.assertIn(loss, retained['unavailable'])
        dense_row = next(frame for frame in result['frames'] if frame['decodedTimeSeconds'] == 0.2)
        self.assertIn(diagnostic_loss, dense_row['unavailable'])
        self.assertNotIn(0.2, {frame['timeSeconds'] for frame in adoption.common.selected_frames(result)})
        self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_tracking_loss_without_exact_actual_exposure_refuses_without_inventing_pts(self):
        document = historical_document(adoption.common.VIDEO_IDS[0])
        original = copy.deepcopy(document['frames'])
        document['trackingLosses'] = [{'featureId': 'unidentified-tip', 'shotId': 'machine',
                                      'decodedTimeSeconds': 0.050001, 'pixel': None}]
        with self.assertRaises(ValueError):
            adoption.adopt_video(document['source']['videoId'], self.association(),
                                  self.write_historical(document))
        self.assertEqual(document['frames'], original)


class ObservationPublicationTests(unittest.TestCase):
    def prepared(self):
        model = adoption.common.current_model_identity()
        return {video_id: {'model': copy.deepcopy(model), 'source': {'videoId': video_id},
                           'frames': [{'decodedTimeSeconds': 0.0}]}
                for video_id in adoption.common.VIDEO_IDS}

    def snapshot(self, root):
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def publication(self, root):
        root.mkdir()
        (root / 'family-packet.json').write_bytes(b'{"chosen":"existing-family"}\n')
        for video_id in adoption.common.VIDEO_IDS:
            (root / f'{video_id}.observations.json').write_bytes(b'original publication\n')

    def test_complete_transaction_refuses_mismatched_model_video_or_missing_video_untouched(self):
        for mismatch in ('model', 'video', 'missing-video'):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'v39'
                self.publication(root)
                before = self.snapshot(root)
                prepared = self.prepared()
                last = adoption.common.VIDEO_IDS[-1]
                if mismatch == 'model':
                    prepared[last]['model']['sha256'] = '0' * 64
                elif mismatch == 'video':
                    prepared[last]['source']['videoId'] = adoption.common.VIDEO_IDS[0]
                else:
                    del prepared[last]
                with self.assertRaises(ValueError):
                    adoption.publish_observations(prepared, root)
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual({path.name for path in root.parent.iterdir()}, {'v39'})

    def test_complete_transaction_publishes_all_six_and_preserves_family_packets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'v39'
            self.publication(root)
            family_bytes = (root / 'family-packet.json').read_bytes()
            prepared = self.prepared()
            adoption.publish_observations(prepared, root)
            for video_id, expected in prepared.items():
                self.assertEqual(json.loads((root / f'{video_id}.observations.json').read_text()), expected)
            self.assertEqual((root / 'family-packet.json').read_bytes(), family_bytes)
            self.assertEqual({path.name for path in root.parent.iterdir()}, {'v39'})

    def test_failed_directory_commit_restores_whole_previous_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'v39'
            self.publication(root)
            before = self.snapshot(root)
            replace = adoption.os.replace

            def fail_commit(source, target):
                if Path(source).name == 'current' and Path(target) == root:
                    raise OSError('Injected filesystem rename failure')
                return replace(source, target)

            with patch.object(adoption.os, 'replace', fail_commit):
                with self.assertRaises(OSError):
                    adoption.publish_observations(self.prepared(), root)
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual({path.name for path in root.parent.iterdir()}, {'v39'})

    def prepared_tracks(self):
        prepared = self.prepared()
        for track in prepared.values():
            track.update(schemaVersion=1, kind='compact-source-track',
                         stages={str(stage): {'status': 'unmeasured'} for stage in (50, 20, 10, 5)})
        return prepared

    def track_publication(self, root):
        self.publication(root)
        for video_id, previous in self.prepared_tracks().items():
            previous['frames'][0]['decodedTimeSeconds'] = 1.0
            (root / f'{video_id}.source-track.json').write_text(json.dumps(previous))
            (root / f'{video_id}.current-associations.json').write_bytes(
                b'{"chosen":"preserve-current-associations","stageAcceptance":false}\n')

    def test_six_track_transaction_refuses_bad_sixth_identity_or_stage_without_touching_publication(self):
        for mismatch in ('model', 'video', 'stage-pass', 'missing-stage', 'kind', 'missing-video'):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'v39'
                self.track_publication(root)
                before = self.snapshot(root)
                prepared = self.prepared_tracks()
                sixth = adoption.common.VIDEO_IDS[-1]
                if mismatch == 'model':
                    prepared[sixth]['model']['sha256'] = '0' * 64
                elif mismatch == 'video':
                    prepared[sixth]['source']['videoId'] = adoption.common.VIDEO_IDS[0]
                elif mismatch == 'stage-pass':
                    prepared[sixth]['stages']['50'] = {'status': 'passed'}
                elif mismatch == 'missing-stage':
                    del prepared[sixth]['stages']['5']
                elif mismatch == 'kind':
                    prepared[sixth]['kind'] = 'historical-fitted-source-track'
                else:
                    del prepared[sixth]
                with self.assertRaises(ValueError):
                    adoption.publish_tracks(prepared, root)
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual({path.name for path in root.parent.iterdir()}, {'v39'})

    def test_complete_six_track_commit_preserves_observations_and_current_choice_packets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'v39'
            self.track_publication(root)
            track_names = {f'{video_id}.source-track.json' for video_id in adoption.common.VIDEO_IDS}
            preserved = {name: data for name, data in self.snapshot(root).items()
                         if name not in track_names}
            prepared = self.prepared_tracks()
            adoption.publish_tracks(prepared, root)
            for video_id, expected in prepared.items():
                self.assertEqual(json.loads((root / f'{video_id}.source-track.json').read_text()), expected)
            self.assertEqual({name: data for name, data in self.snapshot(root).items()
                              if name not in track_names}, preserved)
            self.assertEqual({path.name for path in root.parent.iterdir()}, {'v39'})

    def test_failed_six_track_directory_commit_restores_tracks_observations_and_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'v39'
            self.track_publication(root)
            before = self.snapshot(root)
            replace = adoption.os.replace

            def fail_commit(source, target):
                if Path(source).name == 'current' and Path(target) == root:
                    raise OSError('Injected track-directory commit failure')
                return replace(source, target)

            with patch.object(adoption.os, 'replace', fail_commit):
                with self.assertRaises(OSError):
                    adoption.publish_tracks(self.prepared_tracks(), root)
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual({path.name for path in root.parent.iterdir()}, {'v39'})


if __name__ == '__main__':
    unittest.main()
