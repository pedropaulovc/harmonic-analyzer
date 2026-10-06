"""Replay a complete current native CPU snapshot; never source or GPU proof.

CLI: python current-first-surface.py --header HEADER.json --queries QUERIES.json
Requires numpy from source-fit-requirements.txt. The exporter writes the actual
leased manifest/context and packed buffers, not reconstructed/rest geometry.
HEADER is {manifest, context, scopeAuthority, files:[{primitiveId,name,filename,
arrayType,byteLength,sha256}]}; every manifest buffer, including spring
attributes, is required. scopeAuthority retains the whole actual approved model
descriptor, actual exported NATIVE_RUNTIME_INSTANCES, and sourceConsumerInputs
{path,sha256,scope} receipts, whose CRLF-to-LF bytes must match current disk.
--model-representation can select an isolated approved descriptor; by default
it is this web tree's content/model-representation.json. Approved drawableCount
and the actual runtime creation ledger, not fixed numeric census constants,
bound the full scope. Spring census derives all actual deformation rows/attrs.
The report bridge separately requires canonical consumer seals before calling
this diagnostic CLI; current-disk receipts alone are not source approval.
QUERIES is {headerSha256, metadata, queries:[{queryId,primitiveId,
localCoordinate,origin,direction,near,far}]}. metadata is the actual current
readNativeDrawMetadata() result and must match this header's complete identity.
The SHA256 binds the request to the exact exported header bytes. This validates
an exported current draw, not continued freshness after the live lease expires.

One read-only full-scope load serves the entire batch. stdout is one strict JSON
object; a bad header/batch exits nonzero with a diagnostic only on stderr. An
invalid individual query has result:null and error:string, without erasing valid
siblings. Results retain the original guard schema; the envelope retains actual
metadata/context, every validated buffer receipt, and each normalized ray.

Coordinates use exact numeric stored Float32 equality (including signed-zero
seam rows); queries are never cast to Float32 and vertices are never welded.
Near/far are positive distances along the normalized actual current camera ray,
not camera Z. The independent residual boundary remains 1e-7 metres. The guard's
CPU enum cannot certify GPU rounding, raster visibility or source qualification;
unsupported raster modes explicitly limit its ray proof.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

RESIDUAL_M = 1e-7
GPU_REQUIRED = 'independent-gpu-rounding-raster-and-first-surface-proof-required'
SAFETY = {'sourceQualification': 'not-performed',
          'gpuSafety': 'unmeasured-independent-proof-required',
          'worldCoordinatePrecision': 'float64-cpu-not-exact-gpu',
          'gpuRoundingBoundMetres': None, 'rasterFirstSurfaceCertificate': False,
          'genericApproval': False}
BUFFER_TYPES = {'localPositions': ('Float32Array', '<f4', 3),
                'indices': ('Uint32Array', '<u4', 1),
                'worldPositions': ('Float64Array', '<f8', 3),
                'springCoordinate': ('Float32Array', '<f4', 2),
                'springRestCentre': ('Float32Array', '<f4', 3),
                'springRestTangent': ('Float32Array', '<f4', 3)}
CORE_BUFFERS = {'localPositions', 'indices', 'worldPositions'}
SPRING_BUFFERS = {'springCoordinate', 'springRestCentre', 'springRestTangent'}
IDENTITY_FIELDS = ('model', 'machineRevision', 'inventoryRevision', 'input',
                   'draw', 'census', 'runtimeInstanceDeclarations')
SOURCE_INPUTS = frozenset(('web/src/source-assembly.ts', 'web/src/native-primitive-snapshot.ts',
                           'web/src/scene.ts', 'web/scripts/current-first-surface.py',
                           'web/content/model-representation.json'))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name):
    _require(type(value) is int and value >= 0, name + ' must be a nonnegative integer')
    return value


def _text(value, name):
    _require(isinstance(value, str) and bool(value), name + ' must be a nonempty string')
    return value


def _sha256(value, name):
    _require(isinstance(value, str) and len(value) == 64
             and all(c in '0123456789abcdef' for c in value), name + ' must be SHA256 hex')
    return value


def _vector(value, count, name):
    _require(isinstance(value, list) and len(value) == count
             and all(type(v) in (int, float) and math.isfinite(v) for v in value),
             name + ' must contain finite numeric values')
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'Duplicate JSON member: ' + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('Nonfinite JSON number: ' + value)


def _finite_json(value):
    if isinstance(value, float):
        _require(math.isfinite(value), 'Nonfinite JSON number')
    elif isinstance(value, dict):
        for child in value.values():
            _finite_json(child)
    elif isinstance(value, list):
        for child in value:
            _finite_json(child)


def _read_json(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_bad_constant)
    _finite_json(value)
    _require(isinstance(value, dict), 'JSON document must be an object')
    return value, hashlib.sha256(raw).hexdigest()


def _record_key(record):
    return json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _validate_scope_authority(header, representation_path):
    approved, descriptor_sha = _read_json(representation_path)
    authority = header['scopeAuthority']
    _require(authority['modelRepresentation'] == approved, 'Snapshot approved model descriptor differs from current disk')
    _require(approved['schemaVersion'] == 2 and approved['kind'] == 'lossless-web-model-representation'
             and approved['equivalence']['method'] == 'decoded-per-drawable-exact-after-native-identity-v2'
             and _integer(approved['equivalence']['drawableCount'], 'Approved drawable count') > 0,
             'Unsupported approved representation authority')
    manifest = header['manifest']
    model = manifest['model']
    provenance = model['provenance']
    _require(provenance['sourceCommit'] == approved['source']['sourceCommit']
             and provenance['sourceSha256'] == approved['source']['sha256']
             and provenance['representationKind'] == approved['kind']
             and provenance['expectedSha256'] == approved['representation']['sha256']
             and provenance['expectedByteLength'] == approved['representation']['byteLength']
             and model['identityMapSha256'] == approved['identity']['mapSha256']
             and model['canonicalModelSha256'] == approved['identity']['canonicalSha256']
             and model['semanticSha256'] == approved['equivalence']['semanticSha256'],
             'Snapshot model/source/identity tuple differs from approved representation')
    inputs = authority['sourceConsumerInputs']
    _require(isinstance(inputs, list) and bool(inputs), 'Missing current source consumer receipts')
    paths = [receipt['path'] for receipt in inputs]
    _require(len(set(paths)) == len(paths) and SOURCE_INPUTS.issubset(paths), 'Incomplete current source consumer receipt census')
    # The descriptor lives under web/content; all receipts remain repo-relative.
    root = Path(representation_path).resolve().parents[2]
    for receipt in inputs:
        name = _text(receipt['path'], 'Source consumer path')
        _require(not Path(name).is_absolute(), 'Source consumer path must be repo-relative')
        path = (root / name).resolve()
        _require(path.is_relative_to(root), 'Source consumer escapes repository')
        _sha256(receipt['sha256'], 'Source consumer SHA256')
        actual = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        _require(actual == receipt['sha256'], 'Current source consumer bytes differ: ' + name)
    ledger = authority['runtimeInstances']
    _require(isinstance(ledger, dict), 'Missing actual runtime creation ledger')
    declarations = manifest['runtimeInstanceDeclarations']
    fields = ('partPath', 'templatePartPath', 'localGeometryBinding')
    _require(Counter(_record_key({key: declaration[key] for key in fields}) for declaration in declarations)
             == Counter(_record_key(value) for value in ledger.values()),
             'Runtime instance declarations differ from actual creation ledger')
    return approved, descriptor_sha


def _validate_manifest(header, approved):
    manifest = header['manifest']
    context = header['context']
    _require(isinstance(manifest, dict) and isinstance(context, dict), 'Missing snapshot manifest/context')
    _require(type(manifest['schemaVersion']) is int and manifest['schemaVersion'] == 1 and manifest['method'] == 'current-native-cpu-geometry',
             'Not a current native snapshot')
    _require(manifest['worldCoordinatePrecision'] == 'float64-cpu-not-exact-gpu',
             'Unexpected world precision contract')
    _require(manifest['geometricResidualToleranceMetres'] == RESIDUAL_M,
             'Independent geometric tolerance must remain 1e-7m')
    _require(manifest['sourceQualification'] == 'not-performed'
             and manifest['gpuSafety'] == GPU_REQUIRED
             and manifest['cpuVsGpuRoundingBoundMetres'] is None,
             'CPU snapshot cannot contain source approval or inferred GPU bounds')
    _require(manifest['bufferEncoding'] == 'typed-arrays-packed-xyz-no-welding'
             and manifest['bufferByteOrder'] == 'little-endian', 'Unsupported packed buffer encoding/byte order')
    issues = manifest['issues']
    _require(set(issues) == {'bindingFailures', 'currentOverrideMisses'}
             and all(isinstance(value, list) and not value for value in issues.values()),
             'Snapshot has unresolved binding/override issues')
    model = manifest['model']
    _text(model['runtimeRootUuid'], 'Runtime model root')
    for name in ('identityMapSha256', 'canonicalModelSha256', 'semanticSha256'):
        _sha256(model[name], name)
    provenance = model['provenance']
    for name in ('sourceSha256', 'expectedSha256', 'observedSha256'):
        _sha256(provenance[name], name)
    _text(provenance['sourceCommit'], 'Source commit')
    _require(provenance['identity'] == 'matched'
             and provenance['expectedSha256'] == provenance['observedSha256']
             and _integer(provenance['expectedByteLength'], 'Expected model bytes') > 0
             and provenance['observedByteLength'] == provenance['expectedByteLength'],
             'Native model bytes are not identity matched')
    for name in ('machineRevision', 'inventoryRevision'):
        _integer(manifest[name], name)
    draw = manifest['draw']
    for name in ('drawRevision', 'rendererFrame', 'contextRevision'):
        _integer(draw[name], name)
    _text(draw['viewId'], 'Current draw view')
    _require(context['nativeDrawViewId'] == draw['viewId']
             and context['nativeGeometryIssues'] == issues
             and context['sourceAssembly'] == draw['sourceAssembly'], 'Stale snapshot context/draw association')
    _require(context['modelState'] == 'ready' and context['physicsState'] == 'available'
             and context['referenceSeek'] == 'idle', 'Snapshot context is not a completed native frame')
    for name in ('matrixWorld', 'matrixWorldInverse', 'projectionMatrix', 'projectionMatrixInverse'):
        _vector(draw['camera'][name], 16, 'Current camera ' + name)
    _integer(draw['camera']['layersMask'], 'Camera layers')
    primitives = manifest['primitives']
    clones = manifest['runtimeClones']
    _require(isinstance(primitives, list) and isinstance(clones, list), 'Missing full primitive inventory')
    rows = primitives + clones
    census = manifest['census']
    for key in ('artifactPrimitiveCount', 'runtimeClonePrimitiveCount', 'springPrimitiveCount',
                'artifactSpringPrimitiveCount', 'runtimeCloneSpringPrimitiveCount'):
        _integer(census[key], key)
    _require(census['artifactPrimitiveCount'] == approved['equivalence']['drawableCount'],
             'Incomplete current full-scope census: approved artifact drawable count')
    _require(len(primitives) == census['artifactPrimitiveCount']
             and len(clones) == census['runtimeClonePrimitiveCount'], 'Incomplete artifact/runtime clone census')
    ids = [row['id'] for row in rows]
    _require(len(set(ids)) == len(ids), 'Duplicate primitive identities')
    object_ids = [row['objectUuid'] for row in rows]
    _require(len(set(object_ids)) == len(object_ids), 'Duplicate native object identities')
    artifacts = {}
    signatures = set()
    for bucket, scope in ((primitives, 'artifact'), (clones, 'runtime-clone')):
        for row in bucket:
            identity = row['identity']
            canonical = _text(identity['canonicalId'], 'Canonical primitive ID')
            _text(identity['nodePath'], 'Canonical node path')
            signature = tuple(_integer(identity[name], name) for name in
                              ('nativeNodeIndex', 'representationMeshIndex', 'primitiveIndex'))
            _integer(identity['positionAccessor'], 'POSITION accessor')
            if identity['indexAccessor'] is not None:
                _integer(identity['indexAccessor'], 'Index accessor')
            _require(row['scope'] == scope, 'Primitive inventory bucket/scope mismatch')
            if scope == 'artifact':
                _require(row['runtimeInstance'] is None and row['id'] == canonical
                         and canonical not in artifacts and signature not in signatures,
                         'Artifact canonical identity alias')
                artifacts[canonical] = row
                signatures.add(signature)
            else:
                instance = row['runtimeInstance']
                _text(instance['instancePath'], 'Runtime instance path')
                _text(instance['sourcePartPath'], 'Runtime source part path')
                _require(row['id'] == instance['instancePath'] + '::' + canonical
                         and canonical in artifacts, 'Runtime clone identity is not a unique declared instance')
                template = artifacts[canonical]
                _require(identity == template['identity']
                         and row['geometryUuid'] == template['geometryUuid']
                         and row['vertexCount'] == template['vertexCount']
                         and row['indexCount'] == template['indexCount'], 'Runtime clone template geometry mismatch')
            _integer(row['vertexCount'], 'Vertex count')
            _integer(row['indexCount'], 'Index count')
            decoded = row['decodedPosition']
            _require(decoded['componentType'] == 'Float32' and decoded['itemSize'] == 3
                     and decoded['normalized'] is False, 'POSITION must be exact decoded Float32 triples')
            _vector(row['matrixWorld'], 16, 'Primitive matrixWorld')
            deformation = row['deformation']
            if deformation['kind'] == 'native-stock-spring':
                _require(deformation['cpuEvaluation'] == 'float64-existing-native-curve-with-decoded-float32-attributes',
                         'Unknown spring CPU deformation law')
                for name in ('shaderFunctions', 'positionExpression', 'normalExpression'):
                    _text(deformation[name], 'Current spring ' + name)
                _require(deformation['stock'] in ('channel', 'counter')
                         and set(deformation['uniforms']) == {'springLength', 'springRestLength'}
                         and all(type(v) in (int, float) and math.isfinite(v)
                                 for v in deformation['uniforms'].values()), 'Invalid current spring stock/uniforms')
            else:
                _require(deformation == {'kind': 'matrix-only', 'cpuEvaluation': 'float64-matrix-world-on-decoded-float32-position'},
                         'Unknown current CPU deformation')
            required_buffers = CORE_BUFFERS | (SPRING_BUFFERS if deformation['kind'] == 'native-stock-spring' else set())
            _require(set(row['buffers']) == required_buffers
                     and all(row['buffers'][name] == row['id'] + '/' + name for name in required_buffers),
                     'Incomplete or aliased primitive buffer bindings')
            _validate_draw_row(row, draw)
    _require(_integer(census['artifactMeshNodeCount'], 'Artifact mesh-node count')
             == len({row['identity']['nativeNodeIndex'] for row in primitives}), 'Artifact mesh-node census mismatch')
    artifact_springs = sum(row['deformation']['kind'] == 'native-stock-spring' for row in primitives)
    clone_springs = sum(row['deformation']['kind'] == 'native-stock-spring' for row in clones)
    _require(census['artifactSpringPrimitiveCount'] == artifact_springs
             and census['runtimeCloneSpringPrimitiveCount'] == clone_springs
             and census['springPrimitiveCount'] == artifact_springs + clone_springs, 'Incomplete spring census')
    _validate_runtime_bindings(manifest, artifacts, clones)
    submissions = Counter(_record_key(submission) for row in rows for submission in row['renderSubmissions'])
    _require(submissions == Counter(_record_key(submission) for submission in draw['nativeRenderCallbacks']),
             'Draw submission ledger does not match full primitive scope')
    return rows


def _validate_draw_row(row, draw):
    _text(row['objectUuid'], 'Native object UUID')
    _text(row['geometryUuid'], 'Native geometry UUID')
    materials = {material['uuid']: material for material in row['materials']}
    _require(len(materials) == len(row['materials']) and bool(materials), 'Duplicate/missing material identities')
    for material in materials.values():
        _require({'type', 'blending', 'transparent', 'opacity', 'alphaTest', 'alphaHash',
                  'alphaToCoverage', 'wireframe', 'stencilWrite', 'polygonOffset',
                  'depthTest', 'depthWrite', 'colorWrite', 'depthFunc', 'clippingPlanes',
                  'textures', 'programCacheKey'}.issubset(material),
                 'Incomplete current raster material metadata')
        _require(type(material['side']) is int and material['side'] in (0, 1, 2)
                 and type(material['visible']) is bool, 'Invalid current material side/visibility')
    ancestors = row['ancestors']
    _require(bool(ancestors) and ancestors[0]['uuid'] == row['objectUuid'], 'Missing native visibility ancestry')
    visibility = ('hidden-by-self' if not ancestors[0]['visible'] else
                  'hidden-by-ancestor' if any(not ancestor['visible'] for ancestor in ancestors) else 'visible-through-ancestors')
    _require(row['visibility'] == visibility, 'Contradictory draw visibility ancestry')
    _require(row['cameraLayerEligible'] == ((row['layersMask'] & draw['camera']['layersMask']) != 0),
             'Contradictory current camera layers')
    draw_range = row['drawRange']
    start = _integer(draw_range['effectiveStart'], 'Effective draw start')
    count = _integer(draw_range['effectiveCount'], 'Effective draw count')
    _require(start + count <= max(start, row['indexCount']), 'Effective draw range exceeds topology')
    presence = ('excluded-by-visibility' if visibility != 'visible-through-ancestors' else
                'excluded-by-camera-layer' if not row['cameraLayerEligible'] else
                'excluded-by-material' if all(not m['visible'] for m in materials.values()) else
                'excluded-by-draw-range' if count == 0 else
                'native-render-callback-observed' if row['renderSubmissions'] else 'not-submitted-by-native-renderer')
    _require(row['renderedPresence'] == presence, 'Contradictory actual render submission presence')
    for group in row['groups']:
        _integer(group['start'], 'Group start')
        _integer(group['count'], 'Group count')
    for submission in row['renderSubmissions']:
        _require(submission['objectUuid'] == row['objectUuid'] and submission['materialUuid'] in materials,
                 'Submission object/material mismatch')
        _require(submission['group'] is None or submission['group'] in row['groups'],
                 'Submission group absent from actual groups')


def _validate_runtime_bindings(manifest, artifacts, clones):
    declarations = manifest['runtimeInstanceDeclarations']
    paths = set()
    covered = set()
    for declaration in declarations:
        path = declaration['partPath']
        template_path = declaration['templatePartPath']
        _require(path not in paths and declaration['geometryBindingVerified'] is True
                 and declaration['localGeometryBinding'] == 'shared-decoded-native-template-attributes-and-index',
                 'Unverified or duplicate runtime instance declaration')
        paths.add(path)
        expected_templates = {row['id'] for row in artifacts.values()
                              if row['identity']['nodePath'] == template_path
                              or row['identity']['nodePath'].startswith(template_path + '/')}
        instance_rows = [row for row in clones if row['runtimeInstance']['instancePath'] == path]
        expected_instances = {row['id'] for row in instance_rows}
        _require(bool(expected_templates) and bool(expected_instances)
                 and len(declaration['templatePrimitiveIds']) == len(expected_templates)
                 and set(declaration['templatePrimitiveIds']) == expected_templates
                 and len(declaration['instancePrimitiveIds']) == len(expected_instances)
                 and set(declaration['instancePrimitiveIds']) == expected_instances
                 and declaration['templatePrimitiveCount'] == len(expected_templates)
                 and declaration['instancePrimitiveCount'] == len(expected_instances)
                 and len(expected_templates) == len(expected_instances)
                 and {row['identity']['canonicalId'] for row in instance_rows} == expected_templates
                 and all(row['runtimeInstance']['sourcePartPath'] == template_path for row in instance_rows),
                 'Incomplete runtime clone/template binding census')
        covered.update(expected_instances)
    _require(covered == {row['id'] for row in clones}, 'Undeclared runtime clone scope')
    exclusions = manifest['cloneExclusions']
    _require(exclusions['scope'] == 'artifact-census-only'
             and len(exclusions['primitiveIds']) == len(clones)
             and set(exclusions['primitiveIds']) == covered, 'Runtime clones excluded from rendered geometry scope')


def exact_class(local, coordinate):
    coordinate = np.asarray(coordinate, dtype=np.float64)
    if coordinate.shape != (3,) or not np.isfinite(coordinate).all():
        raise ValueError('localCoordinate must be three finite exact stored F32 values')
    # Do not round the query to F32: a nearby double must not silently become apex.
    return np.flatnonzero(np.all(local == coordinate, axis=1))


class CurrentFirstSurface:
    def __init__(self, header_path, model_representation_path=None):
        path = Path(header_path).resolve()
        header, self.header_sha256 = _read_json(path)
        representation_path = (Path(model_representation_path) if model_representation_path is not None
                               else Path(__file__).resolve().parents[1] / 'content/model-representation.json')
        approved, self.model_representation_sha256 = _validate_scope_authority(header, representation_path)
        self.scope_authority = header['scopeAuthority']
        rows = _validate_manifest(header, approved)
        self.manifest = header['manifest']
        self.context = header['context']
        files = {}
        expected = {(row['id'], name) for row in rows for name in row['buffers']}
        for descriptor in header['files']:
            key = (descriptor['primitiveId'], descriptor['name'])
            _require(key not in files, 'Duplicate buffer descriptor')
            files[key] = descriptor
        _require(set(files) == expected, 'Incomplete or extra full-scope buffer descriptors')
        for row in self.manifest['runtimeClones']:
            template_id = row['identity']['canonicalId']
            _require(all(files[(row['id'], name)]['sha256'] == files[(template_id, name)]['sha256']
                         for name in ('localPositions', 'indices')),
                     'Runtime clone decoded buffers differ from actual shared template geometry')
        parts = []
        self.buffer_receipts = []
        self.auxiliary_buffers = []
        for row in rows:
            arrays = {}
            for name in row['buffers']:
                kind, dtype, width = BUFFER_TYPES[name]
                count = row['indexCount'] if name == 'indices' else row['vertexCount'] * width
                descriptor = files[(row['id'], name)]
                filename = _text(descriptor['filename'], 'Buffer filename')
                _require(not Path(filename).is_absolute(), 'Buffer filename must be snapshot-relative')
                file = (path.parent / filename).resolve()
                _require(file.is_relative_to(path.parent) and file.is_file(), 'Buffer escapes or is missing from snapshot directory')
                _require(descriptor['arrayType'] == kind
                         and _integer(descriptor['byteLength'], 'Buffer byte length') == count * np.dtype(dtype).itemsize
                         and file.stat().st_size == descriptor['byteLength'], 'Buffer type/size mismatch')
                _sha256(descriptor['sha256'], 'Buffer SHA256')
                digest = hashlib.sha256()
                with file.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                _require(digest.hexdigest() == descriptor['sha256'], 'Buffer SHA256 mismatch')
                arrays[name] = np.memmap(file, dtype=dtype, mode='r', shape=(count,)) if count else np.empty(0, dtype=dtype)
                arrays[name].flags.writeable = False
                if name in SPRING_BUFFERS:
                    _require(np.isfinite(arrays[name]).all(), 'Invalid current spring attribute')
                    self.auxiliary_buffers.append(arrays[name])
                self.buffer_receipts.append({key: descriptor[key] for key in
                                             ('primitiveId', 'name', 'arrayType', 'byteLength', 'sha256')})
            parts.append((row, arrays['localPositions'].reshape(-1, 3), arrays['indices'], arrays['worldPositions'].reshape(-1, 3)))
        self._prepare(parts)
        self._record_raster_limitations()

    def _prepare(self, parts):
        self.parts = {}
        self.draws = []
        self.limitations = []
        for row, local, indices, world in parts:
            if row['id'] in self.parts:
                raise ValueError('Duplicate primitive identity')
            if not np.isfinite(local).all() or not np.isfinite(world).all() or (len(indices) and indices.max() >= len(local)):
                raise ValueError('Invalid geometry')
            self.parts[row['id']] = (row, local, indices, world)
            if row['renderedPresence'] != 'native-render-callback-observed':
                continue
            if row['visibility'] != 'visible-through-ancestors' or not row['cameraLayerEligible']:
                raise ValueError('Contradictory draw visibility')
            if row['drawMode'] != 'triangles':
                self.limitations.append({'primitiveId': row['id'], 'reason': 'unsupported draw mode '+row['drawMode']})
                continue
            materials = {m['uuid']: m for m in row['materials']}
            for submission in row['renderSubmissions']:
                if submission['objectUuid'] != row['objectUuid']:
                    raise ValueError('Submission object mismatch')
                material = materials[submission['materialUuid']]
                if not material['visible']:
                    continue
                reasons = []
                for key, default in [('transparent',False),('opacity',1),('alphaTest',0),('alphaHash',False),('alphaToCoverage',False),('wireframe',False),('stencilWrite',False),('polygonOffset',False),('depthTest',True),('depthWrite',True),('colorWrite',True),('depthFunc',3)]:
                    if material.get(key, default) != default:
                        reasons.append(key)
                if material.get('clippingPlanes'): reasons.append('clippingPlanes')
                if any(k in material.get('textures', {}) for k in ('alphaMap', 'displacementMap')): reasons.append('alpha/displacement texture')
                if reasons:
                    self.limitations.append({'primitiveId':row['id'], 'materialUuid':material['uuid'], 'reason':'unsupported raster modes: '+','.join(reasons)})
                group = submission['group']
                if group is not None and group not in row['groups']:
                    raise ValueError('Submission group absent from actual groups')
                start = row['drawRange']['effectiveStart']
                end = min(len(indices), start + row['drawRange']['effectiveCount'])
                if group:
                    start = max(start, group['start']); end = min(end, group['start']+group['count'])
                if start % 3:
                    self.limitations.append({'primitiveId':row['id'], 'reason':'unaligned triangle draw start'})
                offsets = np.arange(start, max(start,end-2), 3, dtype=np.int64)
                if not len(offsets): continue
                faces = indices[offsets[:,None]+np.arange(3)]
                triangles = world[faces]
                e1 = triangles[:,1]-triangles[:,0]; e2 = triangles[:,2]-triangles[:,0]
                matrix = np.asarray(row['matrixWorld']).reshape(4,4,order='F')
                flip = -1 if np.linalg.det(matrix[:3,:3]) < 0 else 1
                self.draws.append((row, material, offsets, faces, triangles[:,0], e1, e2, triangles.min(axis=(0,1)), triangles.max(axis=(0,1)), flip))

    def _record_raster_limitations(self):
        # The geometry capture rejects unregistered vertex hooks upstream. This
        # CPU replay still cannot equate nonstandard blending/shaders with pixels.
        for row, *_ in self.parts.values():
            if row['renderedPresence'] != 'native-render-callback-observed':
                continue
            for material in row['materials']:
                if not material['visible']:
                    continue
                reasons = []
                if material.get('blending', 1) not in (0, 1):
                    reasons.append('blending')
                if material.get('type') in ('ShaderMaterial', 'RawShaderMaterial'):
                    reasons.append('custom shader')
                if reasons:
                    self.limitations.append({'primitiveId': row['id'], 'materialUuid': material['uuid'],
                                             'reason': 'unsupported raster modes: ' + ','.join(reasons)})

    def first_surface(self, origin, direction, near=0., far=float('inf')):
        origin = np.asarray(origin, dtype=float); direction = np.asarray(direction, dtype=float)
        if origin.shape != (3,) or direction.shape != (3,) or not np.isfinite(origin).all() or not np.isfinite(direction).all() or np.linalg.norm(direction) == 0 or not 0 <= near < far:
            raise ValueError('Invalid positive ray interval')
        direction = direction / np.linalg.norm(direction)
        hits = []; best = far
        for row, material, offsets, faces, a, e1, e2, low, high, flip in self.draws:
            nz = direction != 0
            if np.any(~nz & ((origin < low) | (origin > high))): continue
            aa = (low[nz]-origin[nz])/direction[nz]; bb = (high[nz]-origin[nz])/direction[nz]
            if max(near, np.minimum(aa,bb).max()) > min(best,np.maximum(aa,bb).min()): continue
            h = np.cross(direction,e2); den = np.einsum('ij,ij->i',e1,h)
            side = material['side']
            ok = (den*flip > 0) if side == 0 else ((den*flip < 0) if side == 1 else den != 0)
            inverse = np.divide(1.,den,out=np.zeros_like(den),where=den != 0)
            s = origin-a; u = np.einsum('ij,ij->i',s,h)*inverse
            q = np.cross(s,e1); v = q@direction*inverse; t = np.einsum('ij,ij->i',e2,q)*inverse
            ok &= (u>=-1e-12)&(v>=-1e-12)&(u+v<=1+1e-12)&(t>0)&(t>=near)&(t<=best)
            valid = np.flatnonzero(ok)
            if not len(valid): continue
            value = float(t[valid].min())
            if value < best: hits = []; best = value
            for ti in valid[t[valid] == best]:
                hits.append({'primitiveId':row['id'], 'identity':row['identity'], 'scope':row['scope'], 'runtimeInstance':row['runtimeInstance'], 'triangleIndex':int(offsets[ti]//3), 'indexOffset':int(offsets[ti]), 'vertexIds':faces[ti].tolist(), 'materialUuid':material['uuid'], 'distanceMetres':best, 'barycentric':[float(1-u[ti]-v[ti]),float(u[ti]),float(v[ti])], 'worldPointMetres':(origin+best*direction).tolist()})
        return hits

    def guard(self, primitive_id, local_coordinate, origin, direction, near=0., far=float('inf')):
        row, local, indices, world = self.parts[primitive_id]
        ids = exact_class(local, local_coordinate)
        if not len(ids): raise ValueError('No exact stored local Float32 target coordinate')
        hits = self.first_surface(origin,direction,near,far)
        class_set = set(ids.tolist())
        for hit in hits:
            hit['targetResidualMetres'] = float(np.linalg.norm(world[ids]-hit['worldPointMetres'],axis=1).min())
            hit['targetClassIncident'] = hit['primitiveId'] == primitive_id and bool(class_set.intersection(hit['vertexIds']))
        accepted = [h['targetClassIncident'] and h['targetResidualMetres'] <= RESIDUAL_M for h in hits]
        eligibility = 'no-positive-surface' if not hits else ('eligible-cpu-exact-local-class' if all(accepted) else ('ambiguous-coincident-first-surfaces' if any(accepted) else 'ineligible-first-surface'))
        return {'eligibility':eligibility, 'targetPrimitiveId':primitive_id, 'targetLocalCoordinate':list(local_coordinate), 'classVertexIds':ids.tolist(), 'geometricResidualToleranceMetres':RESIDUAL_M, 'firstHit':hits[0] if hits else None, 'coincidentClosestHits':hits, 'scope':{'primitiveCount':len(self.parts), 'artifactPrimitiveCount':sum(p[0]['scope']=='artifact' for p in self.parts.values()), 'runtimeClonePrimitiveCount':sum(p[0]['scope']=='runtime-clone' for p in self.parts.values()), 'springPrimitiveCount':sum(p[0]['deformation']['kind']=='native-stock-spring' for p in self.parts.values()), 'drawSubmissionCount':len(self.draws), 'limitations':self.limitations, 'rayProofLimited':bool(self.limitations)}, 'safety':{'sourceQualification':'not-performed', 'gpuSafety':'unmeasured-independent-proof-required', 'worldCoordinatePrecision':'float64-cpu-not-exact-gpu', 'gpuRoundingBoundMetres':None, 'rasterFirstSurfaceCertificate':False, 'genericApproval':False}}

    def batch(self, request):
        _require(request['headerSha256'] == self.header_sha256, 'Query batch header SHA256 mismatch')
        metadata = request['metadata']
        _require(metadata['status'] == 'current-diagnostic-submission'
                 and metadata['method'] == 'current-native-renderer-submission-metadata'
                 and metadata['reason'] is None and metadata['sourceProof'] is False
                 and metadata['sourceAcceptance'] is False and metadata['sourceQualification'] == 'not-performed'
                 and metadata['gpuSafety'] == GPU_REQUIRED, 'Query metadata is not a current diagnostic draw')
        for name in IDENTITY_FIELDS:
            _require(_record_key(metadata[name]) == _record_key(self.manifest[name]), 'Stale or mismatched query metadata: ' + name)
        queries = request['queries']
        _require(isinstance(queries, list) and bool(queries), 'queries must be a nonempty array')
        ids = [_text(query['queryId'], 'Query ID') for query in queries]
        _require(len(set(ids)) == len(ids), 'Duplicate query IDs')
        results = []
        for query in queries:
            entry = {'queryId': query['queryId'], 'ray': None, 'result': None, 'error': None}
            try:
                primitive = _text(query['primitiveId'], 'Target primitive ID')
                _require(primitive in self.parts, 'Unknown target primitive identity')
                _vector(query['localCoordinate'], 3, 'Exact local coordinate')
                _vector(query['origin'], 3, 'Ray origin')
                _vector(query['direction'], 3, 'Ray direction')
                length = float(np.linalg.norm(query['direction']))
                _require(math.isfinite(length) and length > 0, 'Ray direction must have finite positive length')
                near, far = query['near'], query['far']
                _require(type(near) in (int, float) and type(far) in (int, float)
                         and math.isfinite(near) and math.isfinite(far) and 0 <= near < far,
                         'Explicit finite positive ray clipping interval required')
                entry['ray'] = {'origin': query['origin'], 'direction': (np.asarray(query['direction']) / length).tolist(),
                                'near': near, 'far': far}
                entry['result'] = self.guard(primitive, query['localCoordinate'], query['origin'], query['direction'], near, far)
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                entry['error'] = str(error)
            results.append(entry)
        return {'schemaVersion': 1, 'method': 'current-native-cpu-first-surface-batch',
                'headerSha256': self.header_sha256, 'metadata': metadata,
                'manifest': self.manifest, 'context': self.context,
                'scopeAuthority': self.scope_authority,
                'modelRepresentationSha256': self.model_representation_sha256,
                'scopeVerification': {
                    'artifactScopeMechanism': 'current-approved-representation-drawable-count',
                    'runtimeScopeMechanism': 'actual-runtime-creation-ledger-and-template-geometry-bijection',
                    'stockScopeMechanism': 'actual-native-producer-binding-completeness-and-full-approved-artifact-deformation-ledger',
                    'independentStockComponentCount': False},
                'bufferReceipts': self.buffer_receipts, 'results': results, 'safety': dict(SAFETY)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--header', required=True)
    parser.add_argument('--queries', required=True)
    parser.add_argument('--model-representation', type=Path)
    args = parser.parse_args()
    try:
        request, _ = _read_json(args.queries)
        helper = CurrentFirstSurface(args.header, args.model_representation)
        output = helper.batch(request)
        # Serialize fully before writing, so failure never leaves partial JSON.
        encoded = json.dumps(output, separators=(',', ':'), allow_nan=False)
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as error:
        print('current-first-surface: ' + str(error), file=sys.stderr)
        return 1
    print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
