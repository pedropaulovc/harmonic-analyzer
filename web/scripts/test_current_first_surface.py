"""Load-bearing CPU first-surface controls, never a GPU/source certificate.

Run this focused file with the same numpy environment as source-fit scripts.
Fixtures are deliberately small synthetic surfaces, not observations of a live
pose. Live full-scope proof must separately use the production exported frame.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

SCRIPT = Path(__file__).with_name('current-first-surface.py')
SPEC = importlib.util.spec_from_file_location('current_first_surface', SCRIPT)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
MATRIX = np.eye(4).flatten(order='F').tolist()


def primitive(name, local, indices, world=None, *, visible=True, clone_of=None):
    local = np.asarray(local, dtype='<f4').reshape(-1, 3)
    world = np.asarray(local if world is None else world, dtype='<f8').reshape(-1, 3)
    canonical = clone_of or name
    identity = {'canonicalId': canonical, 'nodePath': canonical, 'nativeNodeIndex': 0,
                'representationMeshIndex': 0, 'primitiveIndex': 0, 'gltfMode': 4,
                'positionAccessor': 0, 'indexAccessor': 1}
    row = {'id': name, 'identity': identity, 'scope': 'runtime-clone' if clone_of else 'artifact',
           'runtimeInstance': {'instancePath': name.split('::')[0], 'sourcePartPath': clone_of} if clone_of else None,
           'objectUuid': name + '-object', 'geometryUuid': canonical + '-geometry',
           'vertexCount': len(local), 'indexCount': len(indices),
           'decodedPosition': {'componentType': 'Float32', 'itemSize': 3, 'normalized': False},
           'matrixWorld': list(MATRIX), 'visibility': 'visible-through-ancestors' if visible else 'hidden-by-self',
           'ancestors': [{'uuid': name + '-object', 'visible': visible}], 'layersMask': 1,
           'cameraLayerEligible': True,
           'renderedPresence': 'native-render-callback-observed' if visible else 'excluded-by-visibility',
           'renderSubmissions': [{'objectUuid': name + '-object', 'materialUuid': name + '-material', 'group': None}] if visible else [],
           'drawMode': 'triangles', 'drawRange': {'effectiveStart': 0, 'effectiveCount': len(indices)},
           'groups': [], 'materials': [{'uuid': name + '-material', 'type': 'MeshStandardMaterial', 'visible': True, 'side': 2,
                                       'blending': 1, 'transparent': False, 'opacity': 1, 'alphaTest': 0, 'alphaHash': False,
                                       'alphaToCoverage': False, 'wireframe': False, 'stencilWrite': False, 'polygonOffset': False,
                                       'depthTest': True, 'depthWrite': True, 'colorWrite': True, 'depthFunc': 3,
                                       'clippingPlanes': None, 'textures': {}, 'programCacheKey': 'fixture-standard'}],
           'deformation': {'kind': 'matrix-only', 'cpuEvaluation': 'float64-matrix-world-on-decoded-float32-position'},
           'buffers': {key: name + '/' + key for key in GUARD.CORE_BUFFERS}}
    return row, local, np.asarray(indices, dtype='<u4'), world


def plane(name, z, **options):
    return primitive(name, [[0, 0, z], [1, 0, z], [0, 1, z]], [0, 1, 2], **options)


def replay(*parts):
    helper = GUARD.CurrentFirstSurface.__new__(GUARD.CurrentFirstSurface)
    helper._prepare(parts)
    return helper


def query(primitive_id='target', local=None):
    return {'queryId': 'view/apex', 'primitiveId': primitive_id,
            'localCoordinate': [0, 0, 2] if local is None else local,
            'origin': [0, 0, 0], 'direction': [0, 0, 4], 'near': 0, 'far': 10}


class SurfaceControls(unittest.TestCase):
    def test_exact_float32_class_retains_seams_and_signed_zero_without_query_cast(self):
        local = [[0.5, 0.0, 0], [1, 0, 0], [0.5, 1, 0], [0.5, -0.0, -0.0]]
        part = primitive('target', local, [3, 1, 2])
        helper = replay(part)
        result = helper.guard('target', [0.5, 0, 0], [0.5, 0, -1], [0, 0, 1], 0, 2)
        self.assertEqual(result['classVertexIds'], [0, 3])
        self.assertEqual(result['eligibility'], 'eligible-cpu-exact-local-class')
        self.assertEqual(result['firstHit']['vertexIds'], [3, 1, 2])
        self.assertTrue(np.signbit(part[1][3, 1]))
        for coordinate in ([0.5 + 1e-9, 0, 0], [float(np.nextafter(np.float32(0.5), np.float32(1))), 0, 0]):
            with self.subTest(coordinate=coordinate), self.assertRaisesRegex(ValueError, 'No exact stored'):
                helper.guard('target', coordinate, [0.5, 0, -1], [0, 0, 1])

    def test_closest_surface_uses_positive_actual_ray_clipping_not_target_subset(self):
        helper = replay(plane('farther', 3), plane('target', 2), plane('occluder', 1), plane('zero', 0), plane('behind', -1))
        result = helper.guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 4], 0, 10)
        self.assertEqual(result['eligibility'], 'ineligible-first-surface')
        self.assertEqual(result['firstHit']['primitiveId'], 'occluder')
        self.assertEqual(result['firstHit']['distanceMetres'], 1)
        clipped = helper.guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 4], 1.5, 2)
        self.assertEqual(clipped['eligibility'], 'eligible-cpu-exact-local-class')
        self.assertEqual(clipped['firstHit']['distanceMetres'], 2)
        self.assertEqual(helper.guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 1.5, 1.9)['eligibility'], 'no-positive-surface')

    def test_clone_equal_coordinate_never_aliases_target_primitive(self):
        target = plane('target', 2)
        clone = plane('clone::target', 2, clone_of='target')
        tied = replay(target, clone).guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 0, 3)
        self.assertEqual(tied['eligibility'], 'ambiguous-coincident-first-surfaces')
        self.assertEqual([h['targetClassIncident'] for h in tied['coincidentClosestHits']], [True, False])
        self.assertEqual(tied['coincidentClosestHits'][1]['scope'], 'runtime-clone')
        target[0]['renderedPresence'] = 'excluded-by-visibility'
        rejected = replay(target, clone).guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 0, 3)
        self.assertEqual(rejected['eligibility'], 'ineligible-first-surface')
        self.assertFalse(rejected['firstHit']['targetClassIncident'])

    def test_one_ulp_neighbor_triangle_is_not_exact_class_topology(self):
        neighbor = float(np.nextafter(np.float32(0.5), np.float32(1)))
        helper = replay(primitive('target', [[0.5, 0, 1], [neighbor, 0, 1], [1, 0, 1], [neighbor, 1, 1]], [1, 2, 3]))
        result = helper.guard('target', [0.5, 0, 1], [neighbor, 0, 0], [0, 0, 1], 0, 2)
        self.assertLess(result['firstHit']['targetResidualMetres'], 1e-7)
        self.assertEqual(result['classVertexIds'], [0])
        self.assertFalse(result['firstHit']['targetClassIncident'])
        self.assertEqual(result['eligibility'], 'ineligible-first-surface')

    def test_residual_boundary_is_independent_of_class_incidence(self):
        helper = replay(plane('target', 1))
        for distance, expected in ((1e-7, 'eligible-cpu-exact-local-class'),
                                   (float(np.nextafter(1e-7, float('inf'))), 'ineligible-first-surface')):
            with self.subTest(distance=distance):
                result = helper.guard('target', [0, 0, 1], [distance, 0, 0], [0, 0, 1], 0, 2)
                self.assertTrue(result['firstHit']['targetClassIncident'])
                self.assertEqual(result['firstHit']['targetResidualMetres'], distance)
                self.assertEqual(result['eligibility'], expected)
                self.assertEqual(result['geometricResidualToleranceMetres'], 1e-7)
                self.assertIsNone(result['safety']['gpuRoundingBoundMetres'])
                self.assertEqual(result['safety']['sourceQualification'], 'not-performed')

    def test_actual_group_draw_range_and_material_side_control_occlusion(self):
        occluder = primitive('occluder', [[0, 0, 1], [1, 0, 1], [0, 1, 1], [5, 5, 1], [6, 5, 1], [5, 6, 1]], [0, 1, 2, 3, 4, 5])
        row = occluder[0]
        group = {'start': 3, 'count': 3, 'materialIndex': 0}
        row['groups'] = [group]
        row['renderSubmissions'][0]['group'] = group
        self.assertEqual(replay(plane('target', 2), occluder).guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 0, 3)['eligibility'], 'eligible-cpu-exact-local-class')
        row['renderSubmissions'][0]['group'] = None
        row['drawRange']['effectiveCount'] = 3
        row['materials'][0]['side'] = 0  # +Z normal viewed from its back by +Z ray.
        self.assertEqual(replay(plane('target', 2), occluder).guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 0, 3)['eligibility'], 'eligible-cpu-exact-local-class')
        row['materials'][0]['side'] = 1
        self.assertEqual(replay(plane('target', 2), occluder).guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 0, 3)['eligibility'], 'ineligible-first-surface')

    def test_unsupported_raster_mode_is_not_hidden_by_cpu_eligibility(self):
        target = plane('target', 2)
        target[0]['materials'][0]['alphaTest'] = 0.5
        result = replay(target).guard('target', [0, 0, 2], [0, 0, 0], [0, 0, 1], 0, 3)
        self.assertEqual(result['eligibility'], 'eligible-cpu-exact-local-class')
        self.assertTrue(result['scope']['rayProofLimited'])
        self.assertIn('alphaTest', result['scope']['limitations'][0]['reason'])
        self.assertFalse(result['safety']['rasterFirstSurfaceCertificate'])


class SnapshotFixture:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.header_path = self.directory / 'header.json'
        self.query_path = self.directory / 'queries.json'
        self.representation_path = self.directory / 'web/content/model-representation.json'
        # Complete declared fixture census, including hidden geometry and clones.
        self.parts = [plane('target', 2)]
        for index in range(1, 4):
            part = plane('part-' + str(index), 3, visible=False)
            for field in ('nativeNodeIndex', 'representationMeshIndex', 'positionAccessor', 'indexAccessor'):
                part[0]['identity'][field] = index
            if index <= 2:
                row = part[0]
                row['deformation'] = {'kind': 'native-stock-spring', 'stock': 'channel',
                                      'uniforms': {'springLength': 0.03, 'springRestLength': 0.03},
                                      'shaderFunctions': 'actual fixture curve', 'positionExpression': 'fixture position',
                                      'normalExpression': 'fixture normal',
                                      'cpuEvaluation': 'float64-existing-native-curve-with-decoded-float32-attributes'}
                row['buffers'].update({name: row['id'] + '/' + name for name in GUARD.SPRING_BUFFERS})
            self.parts.append(part)
        self.parts += [plane('instance-a::target', 2, visible=False, clone_of='target'),
                       plane('instance-b::target', 2, visible=False, clone_of='target')]
        declarations = [{'partPath': instance, 'templatePartPath': 'target',
                         'localGeometryBinding': 'shared-decoded-native-template-attributes-and-index',
                         'templatePrimitiveIds': ['target'], 'instancePrimitiveIds': [instance + '::target'],
                         'templatePrimitiveCount': 1, 'instancePrimitiveCount': 1, 'geometryBindingVerified': True}
                        for instance in ('instance-a', 'instance-b')]
        model = {'runtimeRootUuid': 'native-root', 'identityMapSha256': 'a' * 64,
                 'canonicalModelSha256': 'b' * 64, 'semanticSha256': 'c' * 64,
                 'provenance': {'sourceCommit': 'd' * 40, 'sourceSha256': 'e' * 64,
                                'representationKind': 'lossless-web-model-representation',
                                'expectedSha256': 'f' * 64, 'observedSha256': 'f' * 64,
                                'expectedByteLength': 100, 'observedByteLength': 100, 'identity': 'matched'}}
        draw = {'drawRevision': 5, 'rendererFrame': 9, 'contextRevision': 2, 'viewId': 'view',
                'sourceAssembly': {'kind': 'fixture'},
                'camera': {name: list(MATRIX) for name in ('matrixWorld', 'matrixWorldInverse', 'projectionMatrix', 'projectionMatrixInverse')},
                'nativeRenderCallbacks': self.parts[0][0]['renderSubmissions']}
        draw['camera']['layersMask'] = 1
        issues = {'bindingFailures': [], 'currentOverrideMisses': []}
        census = {'artifactPrimitiveCount': 4, 'artifactMeshNodeCount': 4, 'runtimeClonePrimitiveCount': 2,
                  'springPrimitiveCount': 2, 'artifactSpringPrimitiveCount': 2, 'runtimeCloneSpringPrimitiveCount': 0}
        manifest = {'schemaVersion': 1, 'method': 'current-native-cpu-geometry',
                    'sourceQualification': 'not-performed', 'gpuSafety': GUARD.GPU_REQUIRED,
                    'worldCoordinatePrecision': 'float64-cpu-not-exact-gpu', 'geometricResidualToleranceMetres': 1e-7,
                    'cpuVsGpuRoundingBoundMetres': None, 'bufferEncoding': 'typed-arrays-packed-xyz-no-welding',
                    'bufferByteOrder': 'little-endian', 'model': model, 'machineRevision': 3, 'inventoryRevision': 4,
                    'input': {'actual': [1, 2, 3]}, 'draw': draw, 'issues': issues, 'census': census,
                    'primitives': [part[0] for part in self.parts[:4]], 'runtimeClones': [part[0] for part in self.parts[4:]],
                    'runtimeInstanceDeclarations': declarations,
                    'cloneExclusions': {'scope': 'artifact-census-only', 'primitiveIds': ['instance-a::target', 'instance-b::target']}}
        self.header = {'manifest': manifest,
                       'context': {'nativeDrawViewId': 'view', 'nativeGeometryIssues': issues,
                                   'sourceAssembly': draw['sourceAssembly'], 'modelState': 'ready',
                                   'physicsState': 'available', 'referenceSeek': 'idle'}, 'files': []}
        approved = {'schemaVersion': 2, 'kind': 'lossless-web-model-representation',
                    'source': {'sourceCommit': 'd' * 40, 'sha256': 'e' * 64},
                    'identity': {'mapSha256': 'a' * 64, 'canonicalSha256': 'b' * 64},
                    'representation': {'sha256': 'f' * 64, 'byteLength': 100},
                    'equivalence': {'method': 'decoded-per-drawable-exact-after-native-identity-v2',
                                    'semanticSha256': 'c' * 64, 'drawableCount': 4}}
        self.representation_path.parent.mkdir(parents=True)
        self.representation_path.write_text(json.dumps(approved))
        receipts = []
        for path in sorted(GUARD.SOURCE_INPUTS):
            source_path = self.directory / path
            if source_path != self.representation_path:
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_bytes(b'fixture source\r\n')
            receipts.append({'path': path, 'sha256': hashlib.sha256(source_path.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
                             'scope': 'current-native-diagnostic-source'})
        self.header['scopeAuthority'] = {'modelRepresentation': approved,
                                         'runtimeInstances': {str(index): {name: declaration[name] for name in
                                                                          ('partPath', 'templatePartPath', 'localGeometryBinding')}
                                                              for index, declaration in enumerate(declarations)},
                                         'sourceConsumerInputs': receipts}
        for index, (row, local, indices, world) in enumerate(self.parts):
            arrays = {'localPositions': local, 'indices': indices, 'worldPositions': world}
            if row['deformation']['kind'] == 'native-stock-spring':
                arrays.update({name: np.zeros((len(local), GUARD.BUFFER_TYPES[name][2]), dtype='<f4')
                               for name in GUARD.SPRING_BUFFERS})
            for name, array in arrays.items():
                raw = array.tobytes()
                filename = str(index) + '-' + name + '.bin'
                (self.directory / filename).write_bytes(raw)
                self.header['files'].append({'primitiveId': row['id'], 'name': name, 'filename': filename,
                                             'arrayType': GUARD.BUFFER_TYPES[name][0], 'byteLength': len(raw),
                                             'sha256': hashlib.sha256(raw).hexdigest()})
        self.write()

    def write(self):
        raw = json.dumps(self.header, separators=(',', ':')).encode()
        self.header_path.write_bytes(raw)
        metadata = {name: copy.deepcopy(self.header['manifest'][name]) for name in GUARD.IDENTITY_FIELDS}
        metadata.update({'status': 'current-diagnostic-submission', 'method': 'current-native-renderer-submission-metadata',
                         'reason': None, 'sourceProof': False, 'sourceAcceptance': False,
                         'sourceQualification': 'not-performed', 'gpuSafety': GUARD.GPU_REQUIRED})
        self.request = {'headerSha256': hashlib.sha256(raw).hexdigest(), 'metadata': metadata, 'queries': [query()]}
        self.query_path.write_text(json.dumps(self.request))


class SnapshotRefusalControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = SnapshotFixture(self.temporary.name)

    def load(self):
        return GUARD.CurrentFirstSurface(self.fixture.header_path, self.fixture.representation_path)

    def test_readonly_full_scope_batch_preserves_valid_siblings_and_actual_identity(self):
        helper = self.load()
        self.assertFalse(helper.parts['target'][1].flags.writeable)
        self.assertIsInstance(helper.parts['target'][1], np.memmap)
        with self.assertRaises(ValueError):
            helper.parts['target'][1][0, 0] = 1
        bad = query(local=[1e-9, 0, 2])
        bad['queryId'] = 'view/not-stored'
        self.fixture.request['queries'].append(bad)
        result = helper.batch(self.fixture.request)
        self.assertEqual(result['results'][0]['result']['eligibility'], 'eligible-cpu-exact-local-class')
        self.assertIsNone(result['results'][1]['result'])
        self.assertIn('No exact stored', result['results'][1]['error'])
        self.assertEqual(result['results'][0]['ray']['direction'], [0, 0, 1])
        self.assertEqual(result['results'][0]['result']['scope']['primitiveCount'], 6)
        self.assertIsNone(result['safety']['gpuRoundingBoundMetres'])

    def test_invalid_ray_interval_is_isolated_but_duplicate_query_ids_refuse(self):
        helper = self.load()
        request = copy.deepcopy(self.fixture.request)
        bad = query()
        bad['queryId'] = 'view/bad-clip'
        bad['near'] = 3
        bad['far'] = 2
        request['queries'].append(bad)
        result = helper.batch(request)
        self.assertEqual(result['results'][0]['result']['eligibility'], 'eligible-cpu-exact-local-class')
        self.assertIsNone(result['results'][1]['result'])
        self.assertIn('clipping interval', result['results'][1]['error'])
        request['queries'][1]['queryId'] = request['queries'][0]['queryId']
        with self.assertRaisesRegex(ValueError, 'Duplicate query IDs'):
            helper.batch(request)

    def test_missing_hidden_primitive_clone_or_spring_scope_refuses(self):
        original = copy.deepcopy(self.fixture.header)
        for boundary in ('artifact', 'clone', 'spring', 'descriptor', 'extra-descriptor', 'material'):
            self.fixture.header = copy.deepcopy(original)
            manifest = self.fixture.header['manifest']
            if boundary == 'artifact':
                manifest['primitives'].pop()
                manifest['census']['artifactPrimitiveCount'] -= 1
            elif boundary == 'clone':
                manifest['runtimeClones'].pop()
                manifest['census']['runtimeClonePrimitiveCount'] -= 1
            elif boundary == 'spring':
                manifest['primitives'][1]['deformation'] = copy.deepcopy(manifest['primitives'][0]['deformation'])
            elif boundary == 'descriptor':
                self.fixture.header['files'].pop()
            elif boundary == 'material':
                del manifest['primitives'][0]['materials'][0]['depthTest']
            else:
                descriptor = copy.deepcopy(self.fixture.header['files'][0])
                descriptor['name'] = 'unknown'
                self.fixture.header['files'].append(descriptor)
            self.fixture.write()
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                self.load()

    def test_corrupt_bytes_size_type_and_index_bounds_refuse(self):
        descriptor = self.fixture.header['files'][0]
        file = self.fixture.directory / descriptor['filename']
        original = file.read_bytes()
        file.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            self.load()
        file.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError, 'type/size mismatch'):
            self.load()
        file.write_bytes(original)
        descriptor['arrayType'] = 'Float64Array'
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, 'type/size mismatch'):
            self.load()
        descriptor['arrayType'] = 'Float32Array'
        raw = np.array([0, 1, 3], dtype='<u4').tobytes()
        for index_descriptor in self.fixture.header['files']:
            if index_descriptor['primitiveId'] in ('target', 'instance-a::target', 'instance-b::target') and index_descriptor['name'] == 'indices':
                (self.fixture.directory / index_descriptor['filename']).write_bytes(raw)
                index_descriptor['sha256'] = hashlib.sha256(raw).hexdigest()
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, 'Invalid geometry'):
            self.load()

    def test_clone_shared_geometry_claim_requires_identical_decoded_bytes(self):
        descriptor = next(row for row in self.fixture.header['files']
                          if row['primitiveId'] == 'instance-a::target' and row['name'] == 'localPositions')
        raw = np.array([[0, 0, 2.1], [1, 0, 2], [0, 1, 2]], dtype='<f4').tobytes()
        (self.fixture.directory / descriptor['filename']).write_bytes(raw)
        descriptor['sha256'] = hashlib.sha256(raw).hexdigest()
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, 'clone decoded buffers differ'):
            self.load()

    def test_identity_alias_clone_binding_and_stale_metadata_refuse(self):
        original = copy.deepcopy(self.fixture.header)
        for boundary in ('scope', 'identity', 'clone-template', 'declaration'):
            self.fixture.header = copy.deepcopy(original)
            manifest = self.fixture.header['manifest']
            if boundary == 'scope':
                manifest['primitives'][1]['scope'] = 'runtime-clone'
            elif boundary == 'identity':
                manifest['primitives'][1]['identity'] = copy.deepcopy(manifest['primitives'][0]['identity'])
            elif boundary == 'clone-template':
                manifest['runtimeClones'][0]['geometryUuid'] = 'other-geometry'
            else:
                manifest['runtimeInstanceDeclarations'][0]['instancePrimitiveIds'] = []
            self.fixture.write()
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                self.load()
        self.fixture.header = original
        self.fixture.write()
        helper = self.load()
        for name in GUARD.IDENTITY_FIELDS:
            request = copy.deepcopy(self.fixture.request)
            request['metadata'][name] = None
            with self.subTest(field=name), self.assertRaisesRegex(ValueError, 'Stale or mismatched'):
                helper.batch(request)
        self.fixture.request['headerSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'header SHA256 mismatch'):
            helper.batch(self.fixture.request)

    def test_current_source_bytes_and_approved_descriptor_are_not_caller_counts(self):
        authority = self.fixture.header['scopeAuthority']
        authority['modelRepresentation']['equivalence']['drawableCount'] = 3
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, 'descriptor differs'):
            self.load()
        authority['modelRepresentation']['equivalence']['drawableCount'] = 4
        self.fixture.write()
        source = self.fixture.directory / 'web/src/source-assembly.ts'
        source.write_bytes(b'changed fixture creation ledger\n')
        with self.assertRaisesRegex(ValueError, 'source consumer bytes differ'):
            self.load()

    def test_cli_success_is_json_and_header_failure_has_no_stdout(self):
        command = [sys.executable, str(SCRIPT), '--header', str(self.fixture.header_path), '--queries', str(self.fixture.query_path),
                   '--model-representation', str(self.fixture.representation_path)]
        success = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(success.stderr, '')
        self.assertEqual(json.loads(success.stdout)['results'][0]['result']['eligibility'], 'eligible-cpu-exact-local-class')
        self.fixture.header['files'].pop()
        self.fixture.write()
        failed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(failed.stdout, '')
        self.assertIn('full-scope buffer', failed.stderr)
        self.fixture.query_path.write_text('{"headerSha256":"x","headerSha256":"y"}')
        malformed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(malformed.returncode, 0)
        self.assertEqual(malformed.stdout, '')
        self.assertIn('Duplicate JSON member', malformed.stderr)


if __name__ == '__main__':
    unittest.main()
