import { readFile } from 'node:fs/promises'
import { Matrix3, Matrix4, PerspectiveCamera, PlaneGeometry, Vector3 } from 'three'
import { CURRENT_NATIVE_RAW_SHA256, CURRENT_NATIVE_DELIVERY_SHA256, CURRENT_NATIVE_DELIVERY_BYTES, canonicalJson, jsonDigest, sha256, requireClosed, requireSHA, integer, createNativeByteReader, proveCurrentNativeModelBytes, bindNativeRawPrimitivesToOriginalInventory } from './native-model-byte-proof.mjs'
import { createFiniteCurveWitnessProof, createOriginalCurveWitnessEvaluator, createOriginalSpringNormalReference, createF32EnclosureWorkspace, transportNormalEnclosure, normalError, pointInterval, iadd, imul } from './native-f32-enclosure.mjs'
import { verifyNativeMeshFeatureWitness, nativeHorizontalSections, nativeHeadCapSurfaceSupport } from './native-mesh-feature-witness.mjs'
import { createNativeMaterialProof } from './native-material-proof.mjs'
import { createNativeCameraDomainSummary, qualifyNativeCameraEnclosure, validateNativeCameraSamples, nativeCameraShaderProfile, encloseNativeCameraPoint, encloseNativeViewClipPoint } from './native-camera-enclosure.mjs'
import { frameViews, visibilityProofErrors, witnessErrors } from './verify-reference.mjs'
import { nativeGeometryStateDescriptor, nativeSubmissionStateDescriptor, nativeProgramSource, instrumentNativeVertexShader, serializeNativeBinding, nativeExpectedCameraSnapshot } from '../native-qualification-contract.mjs'
export { instrumentNativeVertexShader } from '../native-qualification-contract.mjs'
export { proveRaster as proveNativeRaster }

const families = ['standard', 'nativeID', 'depth', 'distance']
const bindingKeys = ['sourceVideoId', 'sourceSha256', 'sourceImage', 'decodedFrameIndex', 'decodedTimestampTicks', 'timeBase', 'shotId', 'viewId', 'timeSeconds', 'decodedTimeSeconds', 'modelSourceCommit', 'modelRawSHA256', 'modelDeliverySHA256', 'modelDeliveryByteLength', 'currentBuildClosureSHA256', 'input', 'inputSHA256', 'camera', 'rectSourcePixels', 'presentation', 'composite', 'compositeProvenance', 'imagePlaneWarp', 'resolvedImagePlaneWarp', 'sourceLayout', 'partOverrides', 'sourceDrawRevision', 'completedSceneDrawEpoch']
const POSITION_BOUND = 1e-7
const semanticNames = { position: 'POSITION', normal: 'NORMAL', uv: 'TEXCOORD_0', uv1: 'TEXCOORD_1', color: 'COLOR_0', tangent: 'TANGENT' }
const decodeText = bytes => new TextDecoder('utf-8', { fatal: true }).decode(bytes)
const bytesEqual = (a, b) => a.byteLength === b.byteLength && a.every((value, i) => value === b[i])
const numbersEqual = (a, b) => a.length === b.length && a.every((value, i) => Object.is(value, b[i]) || value === b[i])
const bytesOf = array => new Uint8Array(array.buffer, array.byteOffset, array.byteLength)
function insist(condition, reason) { if (!condition) throw new Error(reason) }
export function nativeProgramSHA256(vertexShader, fragmentShader) { return sha256(nativeProgramSource(vertexShader, fragmentShader)) }
export function nativeGeometryStateSHA256(submitted, vertexShaderText) { return jsonDigest(nativeGeometryStateDescriptor(submitted, vertexShaderText)) }
export function nativeSubmissionStateSHA256(submitted) { return jsonDigest(nativeSubmissionStateDescriptor(submitted)) }
export function closeNativeCodeManifest(codeClosure) {
  insist(codeClosure && Array.isArray(codeClosure.objects) && codeClosure.objects.length > 0, 'Independent current code closure required')
  const urls = new Set()
  const manifest = codeClosure.objects.map(object => {
    insist(typeof object.url === 'string' && object.url && !urls.has(object.url), 'Unique actual code URL required'); urls.add(object.url)
    requireSHA(object.sha256, 'code object hash'); integer(object.byteLength, 'code byte length', 1)
    insist(object.bytes instanceof Uint8Array && object.bytes.byteLength === object.byteLength && sha256(object.bytes) === object.sha256, 'Actual independently supplied current code bytes differ')
    return { url: object.url, sha256: object.sha256, byteLength: object.byteLength }
  }).sort((a, b) => a.url < b.url ? -1 : a.url > b.url ? 1 : 0)
  insist(jsonDigest(manifest) === codeClosure.sha256, 'Independent code manifest hash differs')
  requireSHA(codeClosure.originalSceneClosureSHA256, 'original scene closure')
  return manifest
}
function cameraMatrices(binding, backingWidth, backingHeight, nearFar) {
  const [width, height] = binding.resolvedImagePlaneWarp?.unwarpedViewportPixels ?? binding.rectSourcePixels.slice(2)
  insist(width > 0 && height > 0 && backingWidth > 0 && backingHeight > 0, 'Actual logical/backing view dimensions invalid')
  insist(nearFar?.length === 2 && nearFar.every(Number.isFinite) && nearFar[0] > 0 && nearFar[1] > nearFar[0], 'Frozen original camera near/far convention absent')
  const record = binding.camera, camera = new PerspectiveCamera(record.verticalFovDegrees, width / height, nearFar[0], nearFar[1])
  insist(record.positionMetres?.length === 3 && record.quaternion?.length === 4 && [...record.positionMetres, ...record.quaternion, record.verticalFovDegrees].every(Number.isFinite), 'Independent camera record invalid')
  camera.position.fromArray(record.positionMetres); camera.quaternion.fromArray(record.quaternion).normalize()
  const principal = record.principalPointViewportPixels
  if (principal) camera.setViewOffset(width, height, width / 2 - principal[0], height / 2 - principal[1], width, height)
  camera.updateProjectionMatrix(); camera.updateMatrixWorld(true)
  return { view: camera.matrixWorldInverse, projection: camera.projectionMatrix, inverseProjection: camera.projectionMatrixInverse, world: camera.matrixWorld }
}
function transform(matrix, source, out, w = 1) {
  for (let row = 0; row < 4; row++) out[row] = matrix[row] * source[0] + matrix[row + 4] * source[1] + matrix[row + 8] * source[2] + matrix[row + 12] * w
  return out
}
function fieldSummary() { return { vertexCount: 0, comparedComponentCount: 0, nonfiniteCount: 0, outsideCount: 0, maxAbsoluteError: 0, maxEuclideanError: 0, maxAngularErrorRadians: 0, maxLengthError: 0, maxEnclosureEuclideanBound: 0 } }
function compareNormal(summary, actual, expected, enclosure, scratch) {
  const error = normalError(actual, expected, enclosure, scratch)
  summary.vertexCount++; summary.comparedComponentCount += 3
  for (let i = 0; i < 3; i++) if (!Number.isFinite(actual[i])) summary.nonfiniteCount++
  if (!error.inside || error.angularErrorRadians === null) summary.outsideCount++
  summary.maxEuclideanError = Math.max(summary.maxEuclideanError, error.euclideanError)
  summary.maxLengthError = Math.max(summary.maxLengthError, error.lengthError)
  summary.maxAngularErrorRadians = Math.max(summary.maxAngularErrorRadians, error.angularErrorRadians ?? Math.PI)
  summary.maxEnclosureEuclideanBound = Math.max(summary.maxEnclosureEuclideanBound, error.enclosureEuclideanBound)
}
const uniformTypes = { 5126: [1, 'f32le'], 35664: [2, 'f32le'], 35665: [3, 'f32le'], 35666: [4, 'f32le'], 35674: [4, 'f32le'], 35675: [9, 'f32le'], 35676: [16, 'f32le'], 35685: [6, 'f32le'], 35686: [8, 'f32le'], 35687: [6, 'f32le'], 35688: [12, 'f32le'], 35689: [8, 'f32le'], 35690: [12, 'f32le'], 5124: [1, 'u32le'], 5125: [1, 'u32le'], 35667: [2, 'u32le'], 35668: [3, 'u32le'], 35669: [4, 'u32le'], 35670: [1, 'u32le'], 35671: [2, 'u32le'], 35672: [3, 'u32le'], 35673: [4, 'u32le'], 35678: [1, 'u32le'], 35680: [1, 'u32le'], 36289: [1, 'u32le'], 36293: [1, 'u32le'] }
async function closeActiveUniforms(reader, records) {
  const uniforms = new Map(), arrays = new Map()
  for (const row of records) {
    requireClosed(row, ['name', 'glType', 'arraySize', 'bytes'], 'active uniform')
    insist(typeof row.name === 'string' && !uniforms.has(row.name), 'Duplicate/invalid active uniform'); integer(row.arraySize, 'uniform declared array size', 1)
    const type = uniformTypes[row.glType]; insist(type, 'Uncaptured/unsupported active uniform type')
    const bytes = await reader.span(row.bytes), index = row.name.match(/\[(\d+)\]/), elementCount = index ? 1 : row.arraySize
    insist(bytes.byteLength === type[0] * elementCount * 4, 'Actual per-location active uniform bytes truncated or wrong scalar shape')
    if (row.bytes.scalar !== 'u8') insist(row.bytes.scalar === type[1] && row.bytes.components === type[0] && row.bytes.count === elementCount, 'Active uniform typed span differs')
    const Constructor = type[1] === 'f32le' ? Float32Array : Uint32Array, values = bytes.byteOffset % 4 ? new Constructor(bytes.slice().buffer) : new Constructor(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4)
    insist(values.every(Number.isFinite), 'Nonfinite actual active uniform'); uniforms.set(row.name, values)
    if (index && row.arraySize > 1) {
      const name = row.name.replace(/\[\d+\]/, '[]'), group = arrays.get(name) ?? { count: row.arraySize, indices: new Set() }
      insist(group.count === row.arraySize && +index[1] < group.count && !group.indices.has(+index[1]), 'Actual uniform array declaration/location census differs')
      group.indices.add(+index[1]); arrays.set(name, group)
    }
  }
  for (const group of arrays.values()) insist(group.indices.size === group.count, 'Actual declared uniform array locations absent')
  return uniforms
}
async function proveStatic(reader, manifest, model, poseOracle, codeManifest, oracleFactory) {
  requireClosed(manifest, ['schemaVersion', 'rawSHA256', 'deliverySHA256', 'deliveryByteLength', 'codeObjectSHA256', 'drawables'], 'staticNative')
  insist(manifest.schemaVersion === 1 && manifest.rawSHA256 === model.rawSHA256 && manifest.deliverySHA256 === model.deliverySHA256 && manifest.deliveryByteLength === model.deliveryByteLength, 'Static model identity differs from actual current bytes')
  insist(canonicalJson(await reader.json(manifest.codeObjectSHA256)) === canonicalJson(codeManifest), 'Static code object differs from independent current closure')
  const inventory = new Map(poseOracle.inventory.drawables.map(entry => [entry.path, entry])), result = new Map()
  insist(inventory.size === 462 && manifest.drawables.length === 462, 'Full462 static inventory required')
  insist(manifest.drawables.every((entry, i) => entry.path === poseOracle.inventory.drawables[i].path), 'Ordered static inventory differs from independently frozen original drawables')
  let springCount = 0, springVertices = 0
  for (const entry of manifest.drawables) {
    requireClosed(entry, ['path', 'mode', 'ancestor', 'bindingOwnerPath', 'binding', 'station', 'attributes', 'canonicalIndices', 'restMatrixF64', 'spring'], 'static drawable')
    insist(!result.has(entry.path), 'Duplicate static drawable')
    const primitive = model.primitives.get(entry.path), original = inventory.get(entry.path)
    insist(primitive && original && entry.mode === 4, 'Foreign native drawable')
    requireClosed(entry.ancestor, ['rawNodeIndex', 'rawMeshIndex', 'rawPrimitiveIndex', 'rawPath', 'instanceOf'], 'raw ancestor')
    insist(canonicalJson(entry.ancestor) === canonicalJson({ rawNodeIndex: primitive.nodeIndex, rawMeshIndex: primitive.meshIndex, rawPrimitiveIndex: primitive.primitiveIndex, rawPath: primitive.rawPath, instanceOf: primitive.instanceOf }), 'Invented native ancestry')
    for (const key of ['bindingOwnerPath', 'binding', 'station']) insist(canonicalJson(entry[key]) === canonicalJson(key === 'binding' ? serializeNativeBinding(original[key]) : original[key]), `Independent ${key} differs`)
    const matrix = await reader.numbers(entry.restMatrixF64, { scalar: 'f64le', components: 16, count: 1 })
    insist(numbersEqual(matrix, original.restMatrixF64), 'Static matrix differs from frozen original scene')
    const indices = await reader.numbers(entry.canonicalIndices, { scalar: 'u32le', components: 1, count: primitive.index.length })
    insist(numbersEqual(indices, primitive.index), 'Full ordered raw indices differ')
    const attributes = {}, seen = new Set()
    for (const attribute of entry.attributes) {
      requireClosed(attribute, ['semantic', 'componentType', 'normalized', 'bytes'], 'static attribute')
      const semantic = semanticNames[attribute.semantic] ?? attribute.semantic
      insist(!seen.has(semantic), 'Duplicate static attribute'); seen.add(semantic)
      const authentic = primitive.attributes[semantic]
      insist(authentic && attribute.componentType === authentic.componentType && attribute.normalized === authentic.normalized, 'Static attribute type differs')
      const shape = attribute.bytes.scalar === 'u8' ? { scalar: 'u8', components: 1, count: authentic.bytes.byteLength } : { components: authentic.itemSize, count: authentic.count, scalar: authentic.componentType === 5126 ? 'f32le' : 'u32le' }
      const bytes = await reader.span(attribute.bytes, shape)
      insist(bytesEqual(bytes, authentic.bytes), 'Actual static attribute bytes differ from raw')
      attributes[Object.entries(semanticNames).find(([, rawSemantic]) => rawSemantic === semantic)?.[0] ?? semantic] = authentic
    }
    insist(seen.size === Object.keys(primitive.attributes).length, 'Hidden/static native attribute omitted')
    let springOracle = null, classification = null
    if (original.spring) {
      requireClosed(entry.spring, ['stock', 'restLengthM', 'coordinate', 'restCentre', 'restTangent'], 'spring static')
      insist(entry.spring.stock === original.spring.stock && entry.spring.restLengthM === original.spring.restLengthM, 'Original spring stock/rest differs')
      for (const [name, span, size] of [['springCoordinate', entry.spring.coordinate, 2], ['springRestCentre', entry.spring.restCentre, 3], ['springRestTangent', entry.spring.restTangent, 3]]) attributes[name] = { array: await reader.numbers(span, { scalar: 'f32le', components: size, count: primitive.positions.length / 3 }), count: primitive.positions.length / 3, itemSize: size, componentType: 5126, normalized: false }
      springOracle = oracleFactory(poseOracle.inventory.mechanismData, original.spring.stock, original.spring.restLengthM)
      classification = springOracle.validateClassifiedAttributes(attributes)
      insist(classification.valid && classification.mismatchedComponentCount === 0 && classification.inspectedVertexCount === primitive.positions.length / 3, 'Original exact classifier differs')
      springCount++; springVertices += primitive.positions.length / 3
    } else insist(entry.spring === null, 'Invented spring deformation')
    result.set(entry.path, { primitive, entry, attributes, springOracle, normalReference: springOracle ? createOriginalSpringNormalReference(springOracle) : null, classification, nativeOrdinal: result.size })
  }
  insist(springCount === 21 && springVertices === 3293594, 'Original21/full3293594 spring vertices required')
  return result
}
async function proveSubmitted(reader, submitted, staticEntry, posed, camera) {
  requireClosed(submitted, ['path', 'family', 'vertexShader', 'fragmentShader', 'attributes', 'canonicalSubmittedIndices', 'drawRange', 'activeUniforms', 'matrixWorldF64', 'modelViewF64', 'projectionF64', 'geometryStateSHA256'], 'submitted primitive')
  insist(families.includes(submitted.family), 'Unknown program family')
  requireClosed(submitted.drawRange, ['start', 'count', 'mode'], 'draw range')
  integer(submitted.drawRange.start, 'draw start'); integer(submitted.drawRange.count, 'draw count', 1)
  const { primitive, attributes, springOracle } = staticEntry
  insist(submitted.drawRange.mode === 4 && submitted.drawRange.start % 3 === 0 && submitted.drawRange.count % 3 === 0 && submitted.drawRange.start + submitted.drawRange.count <= primitive.index.length, 'Actual draw range exceeds authentic full triangle indices')
  const indices = await reader.numbers(submitted.canonicalSubmittedIndices, { scalar: 'u32le', components: 1, count: primitive.index.length })
  insist(numbersEqual(indices, primitive.index), 'Full actual submitted index bytes differ')
  const world = await reader.numbers(submitted.matrixWorldF64, { scalar: 'f64le', components: 16, count: 1 }), view = await reader.numbers(submitted.modelViewF64, { scalar: 'f64le', components: 16, count: 1 }), projection = await reader.numbers(submitted.projectionF64, { scalar: 'f64le', components: 16, count: 1 })
  const expectedView = new Matrix4().multiplyMatrices(camera.view, new Matrix4().fromArray(posed.matrixWorld)).elements
  insist(numbersEqual(world, posed.matrixWorld) && numbersEqual(view, expectedView) && numbersEqual(projection, camera.projection.elements), 'Actual matrices differ from independent expected input/camera')
  const vertexShader = decodeText(await reader.span(submitted.vertexShader, { scalar: 'u8', components: 1 })), fragmentShader = decodeText(await reader.span(submitted.fragmentShader, { scalar: 'u8', components: 1 }))
  const names = new Set()
  for (const attribute of submitted.attributes) {
    requireClosed(attribute, ['name', 'componentType', 'normalized', 'stride', 'offset', 'divisor', 'enabled', 'bytes'], 'submitted attribute')
    insist(!names.has(attribute.name), 'Duplicate submitted attribute'); names.add(attribute.name)
    const authentic = attributes[attribute.name]
    insist(authentic && attribute.enabled === true && attribute.divisor === 0 && attribute.componentType === authentic.componentType && attribute.normalized === authentic.normalized, 'Foreign, missing, or disabled active attribute')
    const bytes = await reader.span(attribute.bytes), raw = bytesOf(authentic.array), elementBytes = authentic.itemSize * authentic.array.BYTES_PER_ELEMENT
    integer(attribute.offset, 'active attribute offset'); integer(attribute.stride, 'active attribute stride')
    const stride = attribute.stride || elementBytes
    insist(stride >= elementBytes && attribute.offset % authentic.array.BYTES_PER_ELEMENT === 0 && attribute.offset + (authentic.count - 1) * stride + elementBytes <= bytes.length, 'Actual active attribute layout is truncated')
    if (attribute.bytes.scalar !== 'u8') insist(attribute.bytes.scalar === 'f32le' && attribute.bytes.components === authentic.itemSize && attribute.bytes.count === authentic.count, 'Active attribute typed span shape differs')
    for (let vertex = 0; vertex < authentic.count; vertex++) for (let byte = 0; byte < elementBytes; byte++) insist(bytes[attribute.offset + vertex * stride + byte] === raw[vertex * elementBytes + byte], 'Actual active attribute bytes differ from authentic raw/classifier')
  }
  insist(names.has('position'), 'Missing active original position')
  if (springOracle) for (const name of ['springCoordinate', 'springRestCentre', 'springRestTangent']) insist(names.has(name), 'Missing original spring active input')
  const uniforms = await closeActiveUniforms(reader, submitted.activeUniforms)
  const expectedMatrices = { modelMatrix: world, modelViewMatrix: view, projectionMatrix: projection, normalMatrix: new Matrix3().getNormalMatrix(new Matrix4().fromArray(view)).elements }
  for (const [name, matrix] of Object.entries(expectedMatrices)) if (uniforms.has(name)) insist(numbersEqual(uniforms.get(name), Array.from(matrix, Math.fround)), `Actual ${name} upload differs`)
  insist(uniforms.has('modelViewMatrix') && uniforms.has('projectionMatrix'), 'Original projection input closure incomplete')
  if (springOracle) {
    insist(uniforms.get('springLength')?.[0] === Math.fround(posed.springLengthM) && uniforms.get('springRestLength')?.[0] === Math.fround(staticEntry.entry.spring.restLengthM), 'Actual length upload differs from independent solved input')
    if (uniforms.has('springWorldTranslationLow')) insist(numbersEqual(uniforms.get('springWorldTranslationLow'), [12, 13, 14].map(i => Math.fround(world[i] - Math.fround(world[i])))), 'Actual compensated world translation differs')
  }
  const normalsNeeded = names.has('normal') && uniforms.has('normalMatrix') && !['depth', 'distance'].includes(submitted.family)
  const profile = nativeCameraShaderProfile(vertexShader, { normalsNeeded, spring: Boolean(springOracle) }), worldNeeded = uniforms.has('modelMatrix') && profile.worldNeeded
  if (profile.worldNeeded !== worldNeeded) nativeCameraShaderProfile(vertexShader, { normalsNeeded, worldNeeded, spring: Boolean(springOracle) })
  if (submitted.family === 'nativeID') {
    const id = staticEntry.nativeOrdinal + 1, colour = [id & 255, (id >>> 8) & 255, (id >>> 16) & 255].map(value => Math.fround(value / 255))
    insist(numbersEqual(uniforms.get('nativePathId') ?? [], colour), 'Actual native path ID uniform differs from independent ordered inventory')
    insist(/if\s*\(\s*diffuseColor\.a\s*<=\s*0\.0\s*\)\s*discard\s*;\s*gl_FragColor\s*=\s*vec4\s*\(\s*nativePathId\s*,\s*1\.0\s*\)\s*;\s*}\s*$/.test(fragmentShader), 'Actual native ID shader lacks the original final depth-tested ID epilogue')
  }
  const key = nativeGeometryStateSHA256(submitted, vertexShader)
  insist(key === submitted.geometryStateSHA256, 'Producer semantic state key differs from actual independently closed bytes')
  return { vertexShader, fragmentShader, world, view, projection, uniforms, key, programSHA256: nativeProgramSHA256(vertexShader, fragmentShader), normalsNeeded, worldNeeded }
}
async function closePresentationSubmissions(reader, records, binding, expectedRaster, quadGeometry) {
  const closed = []
  for (const row of records) {
    requireClosed(row, ['kind', 'viewId', 'phase', 'sourceRole', 'vertexShader', 'fragmentShader', 'activeUniforms', 'attributes', 'canonicalSubmittedIndices', 'viewportBackingPixels', 'scissorBackingPixels', 'scissorTest', 'drawRange', 'samplerBindings'], 'presentation submission')
    insist(['source-warp', 'horizontal-mirror', 'source-composite'].includes(row.kind) && row.viewId === binding.viewId && ['source-presentation', 'diagnostic-presentation'].includes(row.phase) && [null, 'native-colour-stage', 'source-composite-image', 'source-composite-sum'].includes(row.sourceRole), 'Foreign presentation draw phase/view/source role')
    requireClosed(row.drawRange, ['start', 'count', 'mode'], 'presentation draw range')
    insist(row.drawRange.start === 0 && row.drawRange.count === 6 && row.drawRange.mode === 4 && numbersEqual(await reader.numbers(row.canonicalSubmittedIndices, { scalar: 'u32le', components: 1, count: 6 }), quadGeometry.index.array), 'Actual presentation indices/range differ from original Three screen quad')
    const names = new Set()
    for (const attribute of row.attributes) {
      requireClosed(attribute, ['name', 'componentType', 'normalized', 'stride', 'offset', 'divisor', 'enabled', 'bytes'], 'presentation attribute')
      const reference = quadGeometry.getAttribute(attribute.name)
      insist(reference && !names.has(attribute.name) && attribute.enabled === true && attribute.divisor === 0 && attribute.componentType === 5126 && attribute.normalized === false, 'Foreign/disabled presentation quad attribute'); names.add(attribute.name)
      const bytes = await reader.span(attribute.bytes), raw = bytesOf(reference.array), width = reference.itemSize * 4, stride = attribute.stride || width
      integer(attribute.offset, 'quad attribute offset'); integer(attribute.stride, 'quad attribute stride')
      insist(stride >= width && attribute.offset % 4 === 0 && attribute.offset + 3 * stride + width <= bytes.length, 'Actual presentation quad attribute layout truncated')
      for (let vertex = 0; vertex < 4; vertex++) for (let byte = 0; byte < width; byte++) insist(bytes[attribute.offset + vertex * stride + byte] === raw[vertex * width + byte], 'Actual quad input bytes differ from original Three geometry')
    }
    insist(names.has('position') && (row.kind === 'source-warp' || names.has('uv')), 'Actual source screen quad inputs absent')
    const vertexShader = decodeText(await reader.span(row.vertexShader, { scalar: 'u8', components: 1 })), fragmentShader = decodeText(await reader.span(row.fragmentShader, { scalar: 'u8', components: 1 })), uniforms = await closeActiveUniforms(reader, row.activeUniforms)
    for (const values of [row.viewportBackingPixels, row.scissorBackingPixels]) insist(values?.length === 4 && values.every(Number.isFinite), 'Actual presentation backing rectangle absent/nonfinite')
    const samplers = new Set()
    for (const sampler of row.samplerBindings) {
      requireClosed(sampler, ['uniform', 'unit', 'boundMatchesMaterialTexture', 'textureUUID', 'textureVersion'], 'presentation sampler')
      insist(!samplers.has(sampler.uniform), 'Duplicate presentation sampler'); samplers.add(sampler.uniform); integer(sampler.unit, 'actual sampler unit')
      insist(uniforms.get(sampler.uniform)?.length === 1 && uniforms.get(sampler.uniform)[0] === sampler.unit, 'Actual uploaded presentation sampler unit differs from observed binding')
      insist(sampler.boundMatchesMaterialTexture === null || typeof sampler.boundMatchesMaterialTexture === 'boolean', 'Invalid actual sampler/material texture relation')
      if (sampler.textureVersion !== null) integer(sampler.textureVersion, 'actual texture version')
    }
    const image = row.samplerBindings.find(sampler => sampler.uniform === 'image')
    const eligible = row.phase === 'source-presentation' && row.sourceRole === 'native-colour-stage' && image?.boundMatchesMaterialTexture === true && typeof image.textureUUID === 'string' && image.textureUUID.length > 0 && expectedRaster && numbersEqual(row.viewportBackingPixels, expectedRaster.destinationViewportBackingPixels) && numbersEqual(row.scissorBackingPixels, expectedRaster.destinationScissorBackingPixels) && row.scissorTest === true
    closed.push({ kind: row.kind, eligible, vertexShader, fragmentShader, uniforms })
  }
  const source = closed.filter(row => row.eligible), warp = source.filter(row => row.kind === 'source-warp' && row.uniforms.get('mask')?.[0] === 0 && row.uniforms.get('warped')?.[0] === Number(Boolean(binding.resolvedImagePlaneWarp))), mirror = source.filter(row => row.kind === 'horizontal-mirror')
  return { ...(expectedRaster ?? {}), warpSubmission: warp.at(-1) ?? null, mirrorSubmission: mirror.at(-1) ?? null }
}
const cameraFields = new Set(['view', 'clip', 'viewNormal'])
const outputFields = new Set(['local', 'world', 'view', 'clip', 'objectNormal', 'viewNormal', 'springCentre', 'springTangent'])
function physicalOutputDescriptor(outputs) {
  return outputs.map(({ unavailable, ...output }) => ({ ...output, unavailable: unavailable.filter(row => !cameraFields.has(row.field)) }))
}
async function closeNumericOutputs(reader, outputs, submitted, closed) {
  const fields = new Map(), count = submitted ? submitted._vertexCount : null
  for (const output of outputs) {
    requireClosed(output, ['path', 'family', 'geometryStateSHA256', 'submissionStateSHA256', 'authority', 'originalProgramSHA256', 'instrumentationSource', 'output', 'fields', 'unavailable'], 'numeric output')
    insist(output.authority === 'epilogue-only-original-active-inputs' && output.path === submitted.path && output.family === submitted.family && output.geometryStateSHA256 === closed.key && output.originalProgramSHA256 === closed.programSHA256, 'Actual numeric output program/input state differs')
    const cameraBatch = output.fields.some(field => cameraFields.has(field.name))
    insist(cameraBatch ? output.submissionStateSHA256 === closed.fullKey : output.submissionStateSHA256 === null, 'Camera output belongs to a different complete actual submission')
    const empty = output.fields.length === 0, stride = output.output.components, occupied = new Set()
    const actual = await reader.numbers(output.output, { scalar: 'f32le', count: empty ? 0 : count })
    for (const field of output.fields) {
      requireClosed(field, ['name', 'offset', 'components'], 'output field'); integer(field.offset, 'field offset')
      insist(!fields.has(field.name) && outputFields.has(field.name) && field.components === (field.name === 'clip' ? 4 : 3), 'Invalid duplicate/shape output field across batches')
      for (let i = 0; i < field.components; i++) { insist(!occupied.has(field.offset + i) && field.offset + i < stride, 'Overlapping/truncated output fields'); occupied.add(field.offset + i) }
      fields.set(field.name, { ...field, actual, stride })
    }
    insist(empty ? actual.length === 0 && stride === 1 : occupied.size === stride, 'Output stride has missing/truncated components')
    const unavailableNames = new Set()
    for (const unavailable of output.unavailable) {
      requireClosed(unavailable, ['field', 'reason'], 'unavailable field')
      insist(outputFields.has(unavailable.field) && !unavailableNames.has(unavailable.field) && !output.fields.some(field => field.name === unavailable.field) && ['not-consumed', 'optimized-out', 'uncaptured-replica-input', 'not-selected-for-measured-tf'].includes(unavailable.reason), 'Invalid unavailable field')
      unavailableNames.add(unavailable.field)
    }
    const instrumentation = decodeText(await reader.span(output.instrumentationSource, { scalar: 'u8', components: 1 }))
    insist(instrumentation === instrumentNativeVertexShader(closed.vertexShader, output.fields), 'Numeric replica changed original shader body or uses nonoriginal epilogue')
  }
  return fields
}
function readOutput(field, index, out) { const start = index * field.stride + field.offset; for (let axis = 0; axis < field.components; axis++) out[axis] = field.actual[start + axis]; return out }
function compareOutputPosition(summary, field, index, expected) {
  let squared = 0; summary.vertexCount++
  const start = index * field.stride + field.offset
  for (let axis = 0; axis < field.components; axis++) {
    summary.comparedComponentCount++
    const actual = field.actual[start + axis], error = Math.abs(actual - expected[axis])
    if (!Number.isFinite(actual) || !Number.isFinite(expected[axis])) { summary.nonfiniteCount++; continue }
    squared += error * error; summary.maxAbsoluteError = Math.max(summary.maxAbsoluteError, error)
    if (error > POSITION_BOUND) summary.outsideCount++
  }
  summary.maxEuclideanError = Math.max(summary.maxEuclideanError, Math.sqrt(squared))
}
async function proveNumeric(reader, outputs, submitted, closed, staticEntry, posed) {
  const count = staticEntry.primitive.positions.length / 3
  const fields = await closeNumericOutputs(reader, outputs, { ...submitted, _vertexCount: count }, closed)
  const needed = ['local', ...(closed.worldNeeded ? ['world'] : []), ...(closed.normalsNeeded ? ['objectNormal'] : []), ...(closed.normalsNeeded && staticEntry.springOracle ? ['springCentre', 'springTangent'] : [])]
  const missing = needed.filter(name => !fields.has(name))
  if (missing.length) return { gaps: missing.map(name => `${submitted.path}/${submitted.family}: needed ${name} actual bytes absent`), failures: [], fields: {}, vertexCount: 0 }
  const summaries = { local: fieldSummary(), ...(closed.worldNeeded ? { world: fieldSummary() } : {}), ...(closed.normalsNeeded ? { objectNormal: fieldSummary() } : {}) }
  const local = new Float64Array(4), world = new Float64Array(4), originalNormal = new Float64Array(3), rawNormal = new Float64Array(3), restTangent = new Float64Array(3), centre = new Float64Array(3), tangent = new Float64Array(3), actualNormal = new Float64Array(3)
  const { attributes, springOracle } = staticEntry, curve = springOracle && closed.normalsNeeded ? createFiniteCurveWitnessProof(springOracle.parameters, posed.springLengthM) : null
  const originalCurve = curve ? createOriginalCurveWitnessEvaluator(springOracle.parameters, posed.springLengthM) : null, originalWitness = { centre: new Float64Array(3), tangent: new Float64Array(3) }
  const normalWorkspace = closed.normalsNeeded ? createF32EnclosureWorkspace() : null, normalScratch = {}
  const localField = fields.get('local'), worldField = fields.get('world'), objectNormalField = fields.get('objectNormal'), centreField = fields.get('springCentre'), tangentField = fields.get('springTangent')
  const localBoundsF64 = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity], localMaxComponentError = [0, 0, 0], branchCounts = { '-2': 0, '-1': 0, '0': 0, '1': 0, '2': 0 }
  let curveOutsideCount = 0, maxCentreErrorMetres = 0, maxTangentError = 0, objectNormalMinOriginalLength = Infinity, objectNormalMaxOriginalLength = 0, objectNormalMaxActualLength = 0, maxNormalReferenceConstructionComponentBound = 0
  if (curve) for (let i = 0; i < count; i++) if (Math.abs(attributes.springCoordinate.array[i * 2]) === 1) curve.observe(attributes.springCoordinate.array[i * 2], attributes.springCoordinate.array[i * 2 + 1], readOutput(centreField, i, centre))
  for (let i = 0; i < count; i++) {
    if (springOracle) { springOracle.deform(attributes, posed.springLengthM, i, local); branchCounts[attributes.springCoordinate.array[i * 2]]++ }
    else for (let axis = 0; axis < 3; axis++) local[axis] = attributes.position.array[i * 3 + axis]
    compareOutputPosition(summaries.local, localField, i, local)
    for (let axis = 0; axis < 3; axis++) { localBoundsF64[axis] = Math.min(localBoundsF64[axis], local[axis]); localBoundsF64[axis + 3] = Math.max(localBoundsF64[axis + 3], local[axis]); localMaxComponentError[axis] = Math.max(localMaxComponentError[axis], Math.abs(localField.actual[i * localField.stride + localField.offset + axis] - local[axis])) }
    if (closed.worldNeeded) { transform(closed.world, local, world); compareOutputPosition(summaries.world, worldField, i, world) }
    if (!closed.normalsNeeded) continue
    for (let axis = 0; axis < 3; axis++) { rawNormal[axis] = attributes.normal.array[i * 3 + axis]; restTangent[axis] = springOracle ? attributes.springRestTangent.array[i * 3 + axis] : axis === 0 ? 1 : 0 }
    let rigid = true
    if (springOracle) {
      staticEntry.normalReference.deformNormal(attributes, posed.springLengthM, i, originalNormal)
      const kind = attributes.springCoordinate.array[i * 2], t = attributes.springCoordinate.array[i * 2 + 1]
      readOutput(centreField, i, centre); readOutput(tangentField, i, tangent); rigid = Math.abs(kind) === 2
      if (!curve.check(kind, t, centre, tangent, restTangent)) curveOutsideCount++
      const original = originalCurve(kind, t, originalWitness)
      if (original) {
        let squared = 0
        for (let axis = 0; axis < 3; axis++) { const error = Math.abs(centre[axis] - staticEntry.normalReference.centre[axis]), delta = tangent[axis] - original.tangent[axis]; maxCentreErrorMetres = Math.max(maxCentreErrorMetres, error); squared += delta * delta; if (error > POSITION_BOUND) curveOutsideCount++ }
        maxTangentError = Math.max(maxTangentError, Math.sqrt(squared))
      }
    } else { originalNormal.set(rawNormal); tangent.set(restTangent) }
    const enclosure = transportNormalEnclosure(rawNormal, restTangent, tangent, rigid, normalWorkspace)
    readOutput(objectNormalField, i, actualNormal); compareNormal(summaries.objectNormal, actualNormal, originalNormal, enclosure, normalScratch)
    const referenceComponentBound = springOracle ? staticEntry.normalReference.constructionComponentBound : 0, referenceVectorBound = Math.sqrt(3) * referenceComponentBound
    maxNormalReferenceConstructionComponentBound = Math.max(maxNormalReferenceConstructionComponentBound, referenceComponentBound)
    summaries.objectNormal.maxEnclosureEuclideanBound = Math.max(summaries.objectNormal.maxEnclosureEuclideanBound, normalScratch.enclosureEuclideanBound + referenceVectorBound)
    objectNormalMinOriginalLength = Math.min(objectNormalMinOriginalLength, Math.max(0, normalScratch.expectedLength - referenceVectorBound)); objectNormalMaxOriginalLength = Math.max(objectNormalMaxOriginalLength, normalScratch.expectedLength + referenceVectorBound)
    objectNormalMaxActualLength = Math.max(objectNormalMaxActualLength, normalScratch.actualLength)
  }
  const failures = Object.entries(summaries).filter(([, row]) => row.nonfiniteCount || row.outsideCount).map(([name]) => `${submitted.path}/${submitted.family}: actual ${name} outside independent numeric proof`)
  if (curveOutsideCount) failures.push(`${submitted.path}/${submitted.family}: centre/tangent witnesses violate original curve/position-coupled normal policy`)
  const cameraDomain = failures.length ? null : createNativeCameraDomainSummary({ localActual: localField, indices: staticEntry.primitive.index, drawRange: submitted.drawRange, localMaxComponentError, localBoundsF64, objectNormalMinOriginalLength: closed.normalsNeeded ? objectNormalMinOriginalLength : null, objectNormalMaxOriginalLength: closed.normalsNeeded ? objectNormalMaxOriginalLength : null, objectNormalMaxActualLength: closed.normalsNeeded ? objectNormalMaxActualLength : null, objectNormalMaxEuclideanErrorBound: summaries.objectNormal?.maxEnclosureEuclideanBound ?? null, vertexCount: count })
  return { gaps: [], failures, fields: summaries, vertexCount: count, geometryStateSHA256: closed.key, originalProgramSHA256: closed.programSHA256, cameraDomain, outputSHA256s: outputs.map(output => output.output.objectSHA256), branchCounts, curveOutsideCount, maxCentreErrorMetres, maxTangentError, maxNormalReferenceConstructionComponentBound, normalReferencePolicy: springOracle && closed.normalsNeeded ? staticEntry.normalReference.policy : 'authentic-original-raw-normal', normalUnits: 'dimensionless; no position-metres tolerance applied', normalPolicy: closed.normalsNeeded ? 'finite-same-program-curve-witness-outward-f32-enclosure-coupled-all-position-1e-7' : 'not-needed' }
}
async function proveSelectedCamera(reader, outputs, submitted, closed, entry, posed, cameraProof) {
  if (!outputs.length) return null
  const count = entry.primitive.positions.length / 3, fields = await closeNumericOutputs(reader, outputs, { ...submitted, _vertexCount: count }, closed)
  const needed = ['view', 'clip', ...(closed.normalsNeeded ? ['viewNormal'] : [])], missing = needed.filter(name => !fields.has(name))
  if (missing.length) return { gaps: missing.map(name => `${submitted.path}/${submitted.family}: selected actual ${name} bytes absent`), failures: [], fields: {}, vertexCount: 0 }
  if (!cameraProof.selectedVertexEnclosure) return { gaps: [`${submitted.path}/${submitted.family}: selected camera lacks prior independent enclosure`], failures: [], fields: {}, vertexCount: 0 }
  const sample = { originalLocal: new Float64Array(3), originalObjectNormal: closed.normalsNeeded ? new Float64Array(3) : null, view: new Float64Array(3), clip: new Float64Array(4), ...(closed.normalsNeeded ? { viewNormal: new Float64Array(3) } : {}) }
  return validateNativeCameraSamples(cameraProof, { vertexCount: count, read(i) {
    if (entry.springOracle) { entry.springOracle.deform(entry.attributes, posed.springLengthM, i, sample.originalLocal); if (closed.normalsNeeded) entry.normalReference.deformNormal(entry.attributes, posed.springLengthM, i, sample.originalObjectNormal) }
    else for (let axis = 0; axis < 3; axis++) { sample.originalLocal[axis] = entry.primitive.positions[i * 3 + axis]; if (closed.normalsNeeded) sample.originalObjectNormal[axis] = entry.primitive.normals[i * 3 + axis] }
    readOutput(fields.get('view'), i, sample.view); readOutput(fields.get('clip'), i, sample.clip); if (closed.normalsNeeded) readOutput(fields.get('viewNormal'), i, sample.viewNormal)
    return sample
  } })
}

// Authentic triangle BVH. Nodes retain only derived bounds and triangle ordinals,
// never world-position exports. Vertex positions are evaluated from raw+F64 law.
function createTriangleBVH(staticEntry, length) {
  const { primitive, springOracle, attributes } = staticEntry, order = Uint32Array.from({ length: primitive.index.length / 3 }, (_, i) => i), nodes = [], a = new Float64Array(3), b = new Float64Array(3), c = new Float64Array(3)
  function vertex(index, out) { if (springOracle) return springOracle.deform(attributes, length, index, out); for (let axis = 0; axis < 3; axis++) out[axis] = primitive.positions[index * 3 + axis]; return out }
  function triangleBounds(ordinal, bounds) {
    vertex(primitive.index[ordinal * 3], a); vertex(primitive.index[ordinal * 3 + 1], b); vertex(primitive.index[ordinal * 3 + 2], c)
    for (let axis = 0; axis < 3; axis++) { bounds[axis] = Math.min(bounds[axis], a[axis], b[axis], c[axis]); bounds[axis + 3] = Math.max(bounds[axis + 3], a[axis], b[axis], c[axis]) }
  }
  function centroid(ordinal, axis) { return (vertex(primitive.index[ordinal * 3], a)[axis] + vertex(primitive.index[ordinal * 3 + 1], b)[axis] + vertex(primitive.index[ordinal * 3 + 2], c)[axis]) / 3 }
  function build(start, end, depth) {
    const bounds = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]
    for (let i = start; i < end; i++) triangleBounds(order[i], bounds)
    const node = { bounds, start, end, left: -1, right: -1 }, index = nodes.length; nodes.push(node)
    if (end - start <= 32 || depth >= 40) return index
    const axis = [0, 1, 2].sort((i, j) => bounds[j + 3] - bounds[j] - (bounds[i + 3] - bounds[i]))[0], pivot = (bounds[axis] + bounds[axis + 3]) / 2
    let lo = start, hi = end - 1
    while (lo <= hi) { if (centroid(order[lo], axis) < pivot) lo++; else { const value = order[lo]; order[lo] = order[hi]; order[hi--] = value } }
    if (lo === start || lo === end) lo = start + Math.floor((end - start) / 2)
    node.left = build(start, lo, depth + 1); node.right = build(lo, end, depth + 1)
    return index
  }
  build(0, order.length, 0)
  return { nodes, order, vertex, primitive }
}
function rayBounds(origin, direction, bounds, maximum) {
  let near = 0, far = maximum
  for (let axis = 0; axis < 3; axis++) {
    if (direction[axis] === 0) { if (origin[axis] < bounds[axis] || origin[axis] > bounds[axis + 3]) return false; continue }
    let a = (bounds[axis] - origin[axis]) / direction[axis], b = (bounds[axis + 3] - origin[axis]) / direction[axis]
    if (a > b) [a, b] = [b, a]
    near = Math.max(near, a); far = Math.min(far, b)
    if (near > far) return false
  }
  return true
}
export function rayTriangle(origin, direction, a, b, c, side) {
  const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]], p = [direction[1] * e2[2] - direction[2] * e2[1], direction[2] * e2[0] - direction[0] * e2[2], direction[0] * e2[1] - direction[1] * e2[0]], det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2]
  if (side === 'front' ? det <= 0 : side === 'back' ? det >= 0 : det === 0) return null
  const inverse = 1 / det, t = [origin[0] - a[0], origin[1] - a[1], origin[2] - a[2]], u = (t[0] * p[0] + t[1] * p[1] + t[2] * p[2]) * inverse
  if (u < 0 || u > 1) return null
  const q = [t[1] * e1[2] - t[2] * e1[1], t[2] * e1[0] - t[0] * e1[2], t[0] * e1[1] - t[1] * e1[0]], v = (direction[0] * q[0] + direction[1] * q[1] + direction[2] * q[2]) * inverse
  if (v < 0 || u + v > 1) return null
  const distance = (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) * inverse
  return distance > 0 ? { distance, barycentric: [1 - u - v, u, v] } : null
}
function nearestTriangle(bvh, origin, direction, side, accept = () => true) {
  let best = null
  const stack = [0], a = new Float64Array(3), b = new Float64Array(3), c = new Float64Array(3)
  while (stack.length) {
    const node = bvh.nodes[stack.pop()]
    if (!rayBounds(origin, direction, node.bounds, best?.distance ?? Infinity)) continue
    if (node.left >= 0) { stack.push(node.left, node.right); continue }
    for (let i = node.start; i < node.end; i++) {
      const triangle = bvh.order[i]
      bvh.vertex(bvh.primitive.index[triangle * 3], a); bvh.vertex(bvh.primitive.index[triangle * 3 + 1], b); bvh.vertex(bvh.primitive.index[triangle * 3 + 2], c)
      const hit = rayTriangle(origin, direction, a, b, c, side)
      if (hit && (!best || hit.distance < best.distance) && accept(triangle, hit)) best = { ...hit, triangleIndex: triangle }
    }
  }
  return best
}
export function unpackNativeDepth(bytes, offset = 0) {
  if (bytes[offset] === 255 && bytes[offset + 1] === 255 && bytes[offset + 2] === 255 && bytes[offset + 3] === 255) return 1
  return bytes[offset] / 256 + bytes[offset + 1] / 65536 + bytes[offset + 2] / 16777216 + bytes[offset + 3] / (255 * 16777216)
}
const unpackDepth = unpackNativeDepth
async function readRasterPlane(reader, plane, encoding) {
  const keys = ['width', 'height', 'origin', 'coordinateSpace', 'viewportBackingPixels', 'encoding', 'depthBits', 'bytes', 'targetSemantics', 'sampleCount', 'textureColorSpace', 'depthAttachment']
  requireClosed(plane, keys, 'raster plane')
  integer(plane.width, 'raster width', 1); integer(plane.height, 'raster height', 1)
  insist(plane.origin === 'bottom-left' && plane.coordinateSpace === 'native-viewport' && plane.encoding === encoding && plane.sampleCount === 0 && plane.viewportBackingPixels?.length === 4, 'Unsupported actual raster target/layout')
  if (encoding === 'three-rgba-depth-v1') insist([16, 24, 32].includes(plane.depthBits) && plane.depthAttachment !== null, 'Actual depth attachment precision required')
  const bytes = await reader.span(plane.bytes, { scalar: 'u8', components: 4, count: plane.width * plane.height })
  return { ...plane, bytes }
}
function proveOriginalSourceEvidence(evidence, binding) {
  const source = evidence.originalSourceBinding ?? evidence
  if (evidence.originalSourceBinding) {
    for (const key of ['sourceVideoId', 'sourceSha256', 'sourceImage', 'decodedFrameIndex', 'decodedTimestampTicks', 'timeBase', 'decodedTimeSeconds', 'shotId', 'viewId']) insist(canonicalJson(source[key]) === canonicalJson(binding[key]), `Original source feature ${key} differs from independently expected exposure/view`)
  } else {
    insist(source.videoId === binding.sourceVideoId && source.sourceSHA256 === binding.sourceSha256 && source.frameIndex === binding.decodedFrameIndex && String(source.decodedTimestampTicks) === binding.decodedTimestampTicks && source.timeBase === binding.timeBase && source.decodedTimeSeconds === binding.decodedTimeSeconds && source.sha256Bgr8 === binding.sourceImage.sha256Bgr8 && source.width === binding.sourceImage.width && source.height === binding.sourceImage.height, 'Frozen original source feature exposure/BGR8 bytes differ')
  }
}
/** Standalone view-point proof only; production uses its full prior camera
 * enclosure, including modelView/local reassociation, in pointEnclosure. */
export function encloseNativeClipPoint(viewPoint, projection, positionBound = POSITION_BOUND) {
  return encloseNativeViewClipPoint(viewPoint, projection, positionBound)
}

/** A fixed pixel intersects a projected triangle plane, not the perturbed
 * original hit point. Finite gradient/determinant intervals include admitted
 * vertex XY/Z movement; a tangent/degenerate interval is unmeasured. */
export function encloseNativeTriangleDepth(triangleNDC, pixelNDC) {
  const ambiguous = reason => ({ status: 'ambiguous', depth: null, reason })
  if (triangleNDC?.length !== 3 || !triangleNDC.every(vertex => vertex?.length === 3 && vertex.every(interval => interval?.length === 2 && interval.every(Number.isFinite) && interval[0] <= interval[1])) || pixelNDC?.length !== 2 || !pixelNDC.every(Number.isFinite)) return ambiguous('finite authentic projected triangle/pixel required')
  const interval = (lower, upper) => {
    const pad = Math.max(Math.abs(lower), Math.abs(upper)) * Number.EPSILON * 32
    return [lower - pad, upper + pad]
  }
  const add = (a, b) => interval(a[0] + b[0], a[1] + b[1]), subtract = (a, b) => interval(a[0] - b[1], a[1] - b[0])
  const multiply = (a, b) => { const products = [a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1]]; return interval(Math.min(...products), Math.max(...products)) }
  const divide = (a, b) => { const quotients = [a[0] / b[0], a[0] / b[1], a[1] / b[0], a[1] / b[1]]; return interval(Math.min(...quotients), Math.max(...quotients)) }
  const [a, b, c] = triangleNDC, first = [0, 1, 2].map(axis => subtract(b[axis], a[axis])), second = [0, 1, 2].map(axis => subtract(c[axis], a[axis]))
  const determinant = subtract(multiply(first[0], second[1]), multiply(first[1], second[0]))
  if (!determinant.every(Number.isFinite) || determinant[0] <= 0 && determinant[1] >= 0) return ambiguous('projected authentic triangle determinant crosses zero')
  const gradient = [
    divide(subtract(multiply(first[2], second[1]), multiply(second[2], first[1])), determinant),
    divide(subtract(multiply(first[0], second[2]), multiply(second[0], first[2])), determinant),
  ]
  const query = pixelNDC.map(value => interval(value, value)), displacement = query.map((value, axis) => subtract(value, a[axis]))
  const z = add(a[2], add(multiply(gradient[0], displacement[0]), multiply(gradient[1], displacement[1])))
  const depth = imul(iadd(z, pointInterval(1)), pointInterval(0.5))
  if (![...gradient.flat(), ...depth].every(Number.isFinite) || depth[0] < 0 || depth[1] > 1) return ambiguous('fixed-pixel authentic triangle depth interval not admitted')
  return { status: 'inside', depth, ndcDeterminantInterval: determinant, ndcDepthGradientIntervals: gradient, policy: 'same-fresh-camera-vertex-clip-enclosure-plus-fixed-pixel-authentic-triangle-plane; no same-point substitution' }
}

async function proveRaster(reader, receipt, expectedDraw, staticEntries, posedMap, camera, bvhCache, materialProof, drawableState, cameraBounds = null, geometryBounds = new Map()) {
  const gaps = [], failures = [], planes = {}
  requireClosed(receipt.raster, ['nativeMaterialRGBA', 'nativeMaterialDepth', 'nativePathID', 'nativeIDDepth'], 'raster')
  for (const [name, encoding] of [['nativeMaterialRGBA', 'rgba8'], ['nativeMaterialDepth', 'three-rgba-depth-v1'], ['nativePathID', 'path-id-rgb24-low-r'], ['nativeIDDepth', 'three-rgba-depth-v1']]) planes[name] = await readRasterPlane(reader, receipt.raster[name], encoding)
  const { nativePathID: id, nativeMaterialDepth: materialDepth, nativeIDDepth: idDepth, nativeMaterialRGBA: material } = planes
  insist(Object.values(planes).every(plane => plane.width === id.width && plane.height === id.height && numbersEqual(plane.viewportBackingPixels, id.viewportBackingPixels)), 'Raster planes have unequal backing views')
  insist(material.targetSemantics === 'actual-production-material-offscreen' && materialDepth.targetSemantics === 'actual-production-material-offscreen' && id.targetSemantics === 'depth-tested-native-id-diagnostic' && idDepth.targetSemantics === 'depth-tested-native-id-diagnostic', 'Raster target semantics are not genuine production/ID planes')
  const paths = [...staticEntries.keys()], pixelCount = id.width * id.height
  let foregroundPixels = 0, invalidPathPixels = 0, depthDisagreements = 0
  const pixelCounts = new Uint32Array(paths.length)
  const quantization = Math.max(1 / (2 ** Math.min(materialDepth.depthBits, idDepth.depthBits) - 1), 2 ** -23) + 2 ** -24
  for (let pixel = 0; pixel < pixelCount; pixel++) {
    const offset = pixel * 4, identifier = id.bytes[offset] + id.bytes[offset + 1] * 256 + id.bytes[offset + 2] * 65536
    if (!identifier) continue
    foregroundPixels++
    if (identifier > paths.length || id.bytes[offset + 3] !== 255 || !posedMap.get(paths[identifier - 1])?.effectiveVisibility || posedMap.get(paths[identifier - 1]).effectiveVisibility === 'hidden') invalidPathPixels++
    if (identifier <= paths.length) pixelCounts[identifier - 1]++
    if (Math.abs(unpackDepth(materialDepth.bytes, offset) - unpackDepth(idDepth.bytes, offset)) > quantization) depthDisagreements++
  }
  if (invalidPathPixels) failures.push('Full native ID plane contains foreign/hidden IDs')
  if (depthDisagreements) failures.push('Production and native ID first-depth planes disagree')
  // Original raw material/image bytes and actual production GPU textures
  // establish side/alpha/clipping, never an asserted opaque body descriptor.
  const body = expectedDraw.bodyProof
  const pathPixelCounts = Object.fromEntries(paths.map((path, i) => [path, pixelCounts[i]]))
  if (!body || !Array.isArray(body.rays)) { gaps.push('Independent current-view authentic ray support proof absent'); return { gaps, failures, pixelCount, foregroundPixels, invalidPathPixels, depthDisagreements, pathPixelCounts, rayCount: 0, witnesses: [], contours: [] } }
  const stateMap = new Map(drawableState.map(row => [row.path, row])), resources = []
  for (const [path, entry] of staticEntries) {
    const pose = posedMap.get(path)
    if (pose.effectiveVisibility === 'hidden' || pose.effectiveVisibility === false) continue
    const actualDescriptors = await Promise.all(stateMap.get(path).materialSlotsSHA256.map(hash => reader.json(hash)))
    const semantics = await materialProof.prove({ primitive: entry.primitive, actualDescriptors, reader, requireDrawBinding: true })
    gaps.push(...semantics.gaps.map(reason => `${path}: ${reason}`)); failures.push(...semantics.failures.map(reason => `${path}: ${reason}`))
    if (semantics.gaps.length || semantics.failures.length) continue
    if (!semantics.depthWrite || !semantics.depthTest || !semantics.colorWrite || semantics.transparent) { gaps.push(`${path}: multilayer/non-depth-writing production surface support unmeasured`); continue }
    const length = entry.springOracle ? pose.springLengthM : null
    let cached = bvhCache.get(path)
    if (!cached || cached.length !== length) {
      let bounds = geometryBounds.get(path) ?? null
      if (!bounds && !entry.springOracle) {
        bounds = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]
        for (let vertex = 0; vertex < entry.primitive.positions.length / 3; vertex++) for (let axis = 0; axis < 3; axis++) {
          const value = entry.primitive.positions[vertex * 3 + axis]
          bounds[axis] = Math.min(bounds[axis], value); bounds[axis + 3] = Math.max(bounds[axis + 3], value)
        }
      }
      cached = { length, bounds, bvh: null }; bvhCache.set(path, cached)
    }
    if (cameraBounds && !cameraBounds.has(path)) { gaps.push(`${path}: same-fresh full camera clip enclosure absent`); continue }
    const matrix = new Matrix4().fromArray(pose.matrixWorld), inverse = matrix.clone().invert()
    resources.push({ path, entry, cached, matrix, inverse, semantics, cameraEnclosure: cameraBounds?.get(path) ?? null })
  }
  function pointEnclosure(resource, worldPoint) {
    return resource.cameraEnclosure
      ? encloseNativeCameraPoint(worldPoint.toArray(), camera, resource.cameraEnclosure)
      : encloseNativeViewClipPoint(worldPoint.clone().applyMatrix4(camera.view).toArray(), camera.projection.elements)
  }
  function nearest(origin, direction, pixelNDC) {
    let best = null
    const ambiguities = []
    for (const resource of resources) {
      const localOrigin = new Vector3().fromArray(origin).applyMatrix4(resource.inverse), localDirection = new Vector3().fromArray(direction).transformDirection(resource.inverse)
      const localOriginArray = localOrigin.toArray(), localDirectionArray = localDirection.toArray()
      if (resource.cached.bounds && !rayBounds(localOriginArray, localDirectionArray, resource.cached.bounds, Infinity)) continue
      resource.cached.bvh ??= createTriangleBVH(resource.entry, resource.cached.length)
      const hit = nearestTriangle(resource.cached.bvh, localOriginArray, localDirectionArray, resource.semantics.sideName, (triangle, candidate) => {
        const point = localOrigin.clone().addScaledVector(localDirection, candidate.distance).applyMatrix4(resource.matrix)
        const clipProof = pointEnclosure(resource, point)
        if (clipProof.status === 'outside') return false
        if (clipProof.status !== 'inside') { ambiguities.push(`${resource.path}/${triangle}: near/frustum/projective support ambiguity`); return false }
        const vertices = [0, 1, 2].map(corner => new Vector3().fromArray(resource.cached.bvh.vertex(resource.entry.primitive.index[triangle * 3 + corner], new Float64Array(3))).applyMatrix4(resource.matrix))
        const vertexEnclosures = vertices.map(vertex => pointEnclosure(resource, vertex))
        if (vertexEnclosures.some(enclosure => !enclosure.projectable)) { ambiguities.push(`${resource.path}/${triangle}: authentic triangle W/near/far ambiguity`); return false }
        const depthProof = encloseNativeTriangleDepth(vertexEnclosures.map(enclosure => enclosure.ndc), pixelNDC)
        if (depthProof.status !== 'inside') { ambiguities.push(`${resource.path}/${triangle}: ${depthProof.reason}`); return false }
        const alpha = resource.semantics.survivesAlpha(triangle, candidate.barycentric)
        if (alpha === null) { ambiguities.push(`${resource.path}/${triangle}: authentic alpha/LOD support unresolved`); return false }
        candidate.clipDepthInterval = depthProof.depth
        candidate.fixedPixelDepthProof = depthProof
        return alpha && (resource.semantics.clippingPlanes ?? []).every(plane => plane[0] * point.x + plane[1] * point.y + plane[2] * point.z + plane[3] >= 0)
      })
      if (!hit) continue
      const point = localOrigin.clone().addScaledVector(localDirection, hit.distance).applyMatrix4(resource.matrix), distance = point.distanceTo(new Vector3().fromArray(origin))
      if (!best || distance < best.distance) best = { ...hit, path: resource.path, worldPointMetres: point.toArray(), distance }
    }
    return { hit: best, ambiguities }
  }
  const checkedRays = new Map(), witnesses = [], contours = []
  for (const ray of body.rays) {
    requireClosed(ray, ['pixel', 'anchorId'], 'expected surface ray')
    insist(typeof ray.anchorId === 'string' && ray.anchorId && !checkedRays.has(ray.anchorId), 'Distinct independently sealed surface ray ID required')
    insist(ray.pixel?.length === 2 && ray.pixel.every(Number.isSafeInteger), 'Independent integer surface pixel required')
    const [x, y] = ray.pixel; insist(x >= 0 && x < id.width && y >= 0 && y < id.height, 'Surface support pixel outside actual target')
    const viewDirection = new Vector3((x + 0.5) / id.width * 2 - 1, (y + 0.5) / id.height * 2 - 1, 0.5).applyMatrix4(camera.inverseProjection).normalize().transformDirection(camera.world)
    const pixelNDC = [(x + 0.5) / id.width * 2 - 1, (y + 0.5) / id.height * 2 - 1]
    const origin = new Vector3().setFromMatrixPosition(camera.world).toArray(), nearestResult = nearest(origin, viewDirection.toArray(), pixelNDC), hit = nearestResult.hit, offset = (y * id.width + x) * 4, identifier = id.bytes[offset] + id.bytes[offset + 1] * 256 + id.bytes[offset + 2] * 65536
    if (nearestResult.ambiguities.length) { gaps.push(...nearestResult.ambiguities.map(reason => `Ray ${ray.anchorId}: ${reason}`)); continue }
    if (!hit || paths[identifier - 1] !== hit.path) { failures.push(`Nearest authentic posed triangle disagrees with GPU ID at ${x},${y}`); continue }
    const point = new Vector3().fromArray(hit.worldPointMetres).applyMatrix4(camera.view).applyMatrix4(camera.projection), depth = point.z * 0.5 + 0.5
    const interval = hit.clipDepthInterval
    insist(interval && interval.every(Number.isFinite) && interval[0] >= 0 && interval[1] <= 1, 'Nearest clip depth interval not admitted')
    const bound = Math.max(depth - interval[0], interval[1] - depth) + quantization
    if ([materialDepth, idDepth].some(plane => { const actual = unpackDepth(plane.bytes, offset); return actual < interval[0] - quantization || actual > interval[1] + quantization })) failures.push(`Nearest authentic triangle depth disagrees at ${x},${y}`)
    checkedRays.set(ray.anchorId, { hit, pixel: ray.pixel, depth, depthBound: bound, depthInterval: interval })
  }
  function surfaceCorrespondence(entry, pose, descriptor, ray) {
    if (!ray) return { status: 'unmeasured', reason: 'actual support ray absent' }
    if (ray.hit.path !== entry.primitive.path || !descriptor.supportTriangleIndices.includes(ray.hit.triangleIndex)) return { status: 'occluded', nearestTriangleIndex: ray.hit.triangleIndex }
    const matrix = new Matrix4().fromArray(pose.matrixWorld), local = new Float64Array(3), scratch = new Float64Array(3)
    if (entry.springOracle) {
      if (descriptor.vertexIndex !== null && descriptor.vertexIndex !== undefined) entry.springOracle.deform(entry.attributes, pose.springLengthM, descriptor.vertexIndex, local)
      else {
        local.fill(0)
        const indices = descriptor.edgeVertexIndices ?? Array.from(entry.primitive.index.subarray(descriptor.triangleIndex * 3, descriptor.triangleIndex * 3 + 3)), weights = descriptor.edgeVertexIndices ? [1 - descriptor.edgeParameter, descriptor.edgeParameter] : descriptor.barycentric
        for (let corner = 0; corner < indices.length; corner++) { entry.springOracle.deform(entry.attributes, pose.springLengthM, indices[corner], scratch); for (let axis = 0; axis < 3; axis++) local[axis] += scratch[axis] * weights[corner] }
      }
    } else local.set(descriptor.localPointMetres)
    const point = new Vector3().fromArray(local).applyMatrix4(matrix), viewPoint = point.clone().applyMatrix4(camera.view)
    const resource = resources.find(row => row.path === entry.primitive.path), clip = pointEnclosure(resource, point)
    if (clip.status !== 'inside') return { status: 'unmeasured', reason: 'feature point clip/domain ambiguity' }
    const projected = viewPoint.clone().applyMatrix4(camera.projection), pixel = [Math.floor((projected.x + 1) * id.width / 2), Math.floor((projected.y + 1) * id.height / 2)]
    insist(numbersEqual(pixel, ray.pixel), 'Raw physical support point projected to a different actual pixel')
    const vertices = [0, 1, 2].map(corner => new Vector3().fromArray(resource.cached.bvh.vertex(entry.primitive.index[ray.hit.triangleIndex * 3 + corner], new Float64Array(3))).applyMatrix4(matrix))
    const normal = vertices[1].clone().sub(vertices[0]).cross(vertices[2].clone().sub(vertices[0]))
    if (!(normal.lengthSq() > 0)) return { status: 'unmeasured', reason: 'degenerate authentic support plane' }
    normal.normalize()
    const origin = new Vector3().setFromMatrixPosition(camera.world), numerator = normal.dot(point.clone().sub(origin)), denominators = [], distances = []
    for (const dx of [0, 1]) for (const dy of [0, 1]) {
      const direction = new Vector3((pixel[0] + dx) / id.width * 2 - 1, (pixel[1] + dy) / id.height * 2 - 1, 0.5).applyMatrix4(camera.inverseProjection).normalize().transformDirection(camera.world)
      const denominator = normal.dot(direction); denominators.push(denominator)
      if (denominator !== 0) { const distance = numerator / denominator; if (!(distance > 0 && Number.isFinite(distance))) return { status: 'unmeasured', reason: 'support pixel-plane denominator not admitted' }; distances.push(origin.clone().addScaledVector(direction, distance).distanceTo(point)) }
    }
    const denominatorError = Number.EPSILON * 64
    if (Math.min(...denominators) - denominatorError <= 0 && Math.max(...denominators) + denominatorError >= 0) return { status: 'unmeasured', reason: 'support pixel footprint crosses plane singularity' }
    const radius = Math.max(...distances) + POSITION_BOUND * 3, discrepancy = new Vector3().fromArray(ray.hit.worldPointMetres).distanceTo(point)
    if (!(Number.isFinite(radius) && discrepancy <= radius)) return { status: 'occluded', reason: 'nearest same-body point outside authentic physical support footprint' }
    return { status: 'visible', triangleIndex: ray.hit.triangleIndex, worldPointMetres: point.toArray(), worldDiscrepancyMetres: discrepancy, pixelFootprintRadiusMetres: radius, depthInterval: ray.depthInterval }
  }
  function triangleSupport(primitive, triangleIndex, barycentric, localPointMetres) {
    integer(triangleIndex, 'support triangle index')
    insist(triangleIndex * 3 + 3 <= primitive.index.length && barycentric?.length === 3 && barycentric.every(value => Number.isFinite(value) && value >= 0) && Math.abs(barycentric.reduce((sum, value) => sum + value, 0) - 1) <= Number.EPSILON * 8, 'Authentic support triangle/barycentric missing')
    const vertices = Array.from(primitive.index.subarray(triangleIndex * 3, triangleIndex * 3 + 3))
    for (let axis = 0; axis < 3; axis++) {
      const expected = vertices.reduce((sum, vertex, corner) => sum + primitive.positions[vertex * 3 + axis] * barycentric[corner], 0)
      const error = vertices.reduce((sum, vertex) => sum + Math.abs(primitive.positions[vertex * 3 + axis]), 0) * Number.EPSILON * 64
      insist(Number.isFinite(localPointMetres[axis]) && Math.abs(expected - localPointMetres[axis]) <= error + Number.MIN_VALUE, 'Support point is not its authentic raw triangle point')
    }
    return vertices
  }
  const featureSupports = new Map()
  for (const support of body.featureSupports ?? []) {
    if (!Object.hasOwn(support, 'raySupports')) { gaps.push(`Witness ${support.anchorId}: actual raw-edge/triangle surface correspondence absent`); continue }
    requireClosed(support, ['anchorId', 'geometryEvidence', 'geometryEvidenceSHA256', 'rayAnchorIds', 'raySupports'], 'sealed native feature footprint')
    const witness = expectedDraw.witnesses?.find(row => row.anchorId === support.anchorId)
    insist(witness && !featureSupports.has(support.anchorId), 'Foreign/duplicate native feature footprint')
    const entry = staticEntries.get(witness.partPath), evidence = support.geometryEvidence, pose = posedMap.get(witness.partPath)
    insist(jsonDigest(evidence) === support.geometryEvidenceSHA256 && evidence.sectionPlaneLocal?.length === 4 && numbersEqual(evidence.sectionPlaneLocal.slice(0, 3), [0, 1, 0]), 'Native support evidence hash/section differs')
    const section = nativeHorizontalSections(entry.primitive, -evidence.sectionPlaneLocal[3])
    const cycle = section.cycles.find(row => canonicalJson(row.triangleIndices) === canonicalJson(evidence.rimTriangleIndices))
    insist(cycle && canonicalJson(cycle.endpoints) === canonicalJson(evidence.rimEndpoints), 'Complete closed rim raw-edge membership differs')
    const topCap = evidence.topCap ? nativeHeadCapSurfaceSupport(entry.primitive) : null
    if (topCap) insist(canonicalJson(topCap) === canonicalJson(evidence.topCap), 'Authentic whole head-cap support construction differs')
    const capCandidates = new Map((topCap?.surfaceSupportPoints ?? []).map(point => [jsonDigest(point), point])), usedCapCandidates = new Set(), visibleSlots = new Set(), outcomes = []
    let visibleRimCount = 0, visibleCapCount = 0, occludedRimCount = 0, unmeasuredRimCount = 0
    for (const row of support.raySupports) {
      insist(support.rayAnchorIds.includes(row.anchorId), 'Physical surface ray omitted from current required support')
      const ray = checkedRays.get(row.anchorId)
      if (row.kind === 'section-edge') {
        requireClosed(row, ['anchorId', 'kind', 'localPointMetres', 'endpointOrdinal', 'rawPositionIds', 'supportingRawEdges', 'parameterFromFirstVertex', 'supportTriangleIndices'], 'raw section-edge ray')
        const endpoint = cycle.endpoints[integer(row.endpointOrdinal, 'raw endpoint ordinal')]
        insist(endpoint && canonicalJson({ localPointMetres: endpoint.localMetres, rawPositionIds: endpoint.rawPositionIds, supportingRawEdges: endpoint.supportingRawEdges, parameterFromFirstVertex: endpoint.parameterFromFirstVertex, supportTriangleIndices: [...new Set(endpoint.supportingRawEdges.map(edge => edge.triangleIndex))].sort((a, b) => a - b) }) === canonicalJson({ localPointMetres: row.localPointMetres, rawPositionIds: row.rawPositionIds, supportingRawEdges: row.supportingRawEdges, parameterFromFirstVertex: row.parameterFromFirstVertex, supportTriangleIndices: row.supportTriangleIndices }), 'Physical rim ray is not its original raw edge/triangle')
        const result = surfaceCorrespondence(entry, pose, { ...row, edgeVertexIndices: endpoint.supportingRawEdges[0].vertexIndices, edgeParameter: endpoint.parameterFromFirstVertex }, ray)
        if (result.status === 'visible') visibleRimCount++; else if (result.status === 'occluded') occludedRimCount++; else unmeasuredRimCount++
        outcomes.push({ anchorId: row.anchorId, kind: row.kind, ...result })
      } else if (row.kind === 'floor-triangle') {
        requireClosed(row, ['anchorId', 'kind', 'triangleIndex', 'vertexIndices', 'barycentric', 'localPointMetres', 'supportTriangleIndices'], 'raw floor triangle ray')
        insist(numbersEqual(triangleSupport(entry.primitive, row.triangleIndex, row.barycentric, row.localPointMetres), row.vertexIndices) && numbersEqual(row.supportTriangleIndices, [row.triangleIndex]) && evidence.floorTriangles.some(triangle => triangle.triangleIndex === row.triangleIndex), 'Floor/slot supporting triangle is not authentic')
        const result = surfaceCorrespondence(entry, pose, row, ray)
        if (result.status === 'visible') visibleSlots.add(row.triangleIndex)
        outcomes.push({ anchorId: row.anchorId, kind: row.kind, ...result })
      } else {
        requireClosed(row, ['anchorId', 'kind', 'candidates'], 'raw head-cap pixel support')
        insist(row.kind === 'head-cap-pixel-support', 'Unknown raw surface support construction')
        for (const point of row.candidates) {
          requireClosed(point, ['construction', 'vertexIndex', 'triangleIndex', 'barycentric', 'localPointMetres', 'supportTriangleIndices'], 'head-cap raw candidate')
          const floor = point.construction === 'actual-native-slot-floor-triangle-centroid'
          if (floor) {
            triangleSupport(entry.primitive, point.triangleIndex, point.barycentric, point.localPointMetres)
            insist(numbersEqual(point.supportTriangleIndices, [point.triangleIndex]) && evidence.floorTriangles.some(triangle => triangle.triangleIndex === point.triangleIndex), 'Foreign raw slot-floor candidate')
          } else { const key = jsonDigest(point); insist(capCandidates.has(key), 'Foreign/nonoriginal cap support point'); usedCapCandidates.add(key) }
          const result = surfaceCorrespondence(entry, pose, point, ray)
          if (result.status === 'visible') { if (floor) visibleSlots.add(point.triangleIndex); else visibleCapCount++ }
          outcomes.push({ anchorId: row.anchorId, construction: point.construction, ...result })
        }
      }
    }
    if (topCap && usedCapCandidates.size !== capCandidates.size) gaps.push(`Witness ${support.anchorId}: complete authentic cap/rim support point census absent`)
    if (!visibleRimCount && !visibleCapCount && visibleSlots.size < 2) gaps.push(`Witness ${support.anchorId}: genuine visible head rim or two distinct slot-floor triangle supports absent`)
    featureSupports.set(support.anchorId, { geometryEvidenceSHA256: support.geometryEvidenceSHA256, rawClosedSection: true, rawEndpointCount: cycle.endpoints.length, visibleRimCount, occludedRimCount, unmeasuredRimCount, visibleCapCount, visibleSlotTriangleIndices: [...visibleSlots], outcomes, scope: 'raw closed axis section separately proven; only matched original physical surface points counted visible' })
  }
  for (const witness of expectedDraw.witnesses ?? []) {
    const entry = staticEntries.get(witness.partPath)
    if (!entry) { failures.push(`Witness ${witness.anchorId} has foreign primitive`); continue }
    try {
      const feature = verifyNativeMeshFeatureWitness(witness, entry.primitive), support = checkedRays.get(witness.anchorId)
      if (!support) { gaps.push(`Witness ${witness.anchorId}: authentic nearest surface support absent`); continue }
      if (support.hit.path !== witness.partPath || !feature.supportTriangleIndices.includes(support.hit.triangleIndex)) failures.push(`Witness ${witness.anchorId}: nearest surface is not authentic feature support`)
      const source = body.sourceFeatures?.find(row => row.anchorId === witness.anchorId)
      if (!source || !expectedDraw.sourceFrame || !expectedDraw.sourceView) gaps.push(`Witness ${witness.anchorId}: independently sealed original source feature association absent`)
      else { insist(jsonDigest(source.evidence) === witness.sourceFeatureEvidenceSHA256, 'Original source feature evidence hash differs'); proveOriginalSourceEvidence(source.evidence, expectedDraw.binding) }
      witnesses.push({ anchorId: witness.anchorId, partPath: witness.partPath, kind: witness.kind, sourceFeatureEvidenceSHA256: witness.sourceFeatureEvidenceSHA256, sourceEvidenceQualified: Boolean(source && expectedDraw.sourceFrame && expectedDraw.sourceView), ...feature, nearestHit: support.hit, pixel: support.pixel, footprint: featureSupports.get(witness.anchorId) ?? null })
    } catch (error) { failures.push(`Witness ${witness.anchorId}: ${error.message}`) }
  }
  for (const contour of body.contours ?? []) {
    requireClosed(contour, ['id', 'partPath', 'sourceFeatureEvidenceSHA256', 'evidence', 'rayAnchorIds'], 'original source contour')
    insist(jsonDigest(contour.evidence) === contour.sourceFeatureEvidenceSHA256 && staticEntries.has(contour.partPath), 'Original source contour hash/native primitive differs')
    proveOriginalSourceEvidence(contour.evidence, expectedDraw.binding)
    const support = contour.rayAnchorIds.map(anchorId => checkedRays.get(anchorId))
    if (!support.length || support.some(ray => !ray)) { gaps.push(`Contour ${contour.id}: complete authentic first-surface support absent`); continue }
    if (support.some(ray => ray.hit.path !== contour.partPath)) { failures.push(`Contour ${contour.id}: nearer authentic surface belongs to another original body`); continue }
    contours.push({ id: contour.id, partPath: contour.partPath, sourceFeatureEvidenceSHA256: contour.sourceFeatureEvidenceSHA256, rayCount: support.length, nearestHits: support.map(ray => ray.hit), status: 'qualified' })
  }
  if (!witnesses.length && !contours.length) gaps.push('Independently sealed native/source feature or genuine contour support absent')
  return { gaps, failures, pixelCount, foregroundPixels, invalidPathPixels, depthDisagreements, pathPixelCounts, rayCount: checkedRays.size, witnesses, contours, qualificationScope: 'same-epoch-offscreen-production-and-diagnostic-ID; no canvas/MSAA equivalence claim' }
}

function freezeComputed(value) {
  if (!value || typeof value !== 'object' || ArrayBuffer.isView(value) || Object.isFrozen(value)) return value
  for (const child of Object.values(value)) freezeComputed(child)
  return Object.freeze(value)
}
function posedFeaturePoint(witness, feature, entry, length, out) {
  if (!entry.springOracle) { out.set(feature.localPointMetres); return out }
  const scratch = new Float64Array(3)
  if (witness.kind === 'mesh-vertex') return entry.springOracle.deform(entry.attributes, length, witness.vertexIndex, out)
  if (witness.kind === 'triangle-point') {
    out.fill(0)
    for (let corner = 0; corner < 3; corner++) {
      entry.springOracle.deform(entry.attributes, length, entry.primitive.index[witness.triangleIndex * 3 + corner], scratch)
      for (let axis = 0; axis < 3; axis++) out[axis] += scratch[axis] * witness.barycentric[corner]
    }
    return out
  }
  throw new Error('Spring section/axis feature pose construction unavailable')
}
/** Fixed is a per-leaf protected world-motion dependency result, not a label
 * inherited from a source assembly or a stationary end/centre feature. */
export function qualifyOriginalNativeFixedLeaf(path, entry, inventory, overrides) {
  const original = inventory?.drawables?.find(row => row.path === path), reasons = [], associatedOverrides = (overrides ?? []).filter(override => path === override.partPath || path.startsWith(`${override.partPath}/`))
  const nonRigidKinds = []
  if (entry?.springOracle || original?.spring) nonRigidKinds.push('original-spring-stock')
  if (original?.object?.isSkinnedMesh) nonRigidKinds.push('original-skinned-geometry')
  if (Object.values(original?.geometry?.morphAttributes ?? {}).some(attributes => attributes.length > 0)) nonRigidKinds.push('original-morph-geometry')
  const owners = new Map((inventory?.drawables ?? []).filter(row => row.bindingOwnerPath && row.binding).map(row => [row.bindingOwnerPath, row.binding]))
  const dynamicAncestors = [...owners].filter(([owner, binding]) => (path === owner || path.startsWith(`${owner}/`)) && binding.motion !== 'paper-fixed').map(([owner, binding]) => ({ owner, motion: binding.motion }))
  if (!original || inventory.closureSHA256 !== 'd3f0bcdeaea5924931d82715ace92e483eb123e0685419ccb5940c06c6730413') reasons.push('Protected admitted original9e72 per-leaf world-motion dependency closure unavailable')
  if (nonRigidKinds.length) reasons.push('Original leaf has nonrigid geometry; a fixed end/centre cannot establish a fixed whole leaf')
  if (original?.binding && original.binding.motion !== 'paper-fixed') reasons.push(`Original ${original.binding.motion} binding is not admitted world-fixed`)
  if (dynamicAncestors.length) reasons.push('Original leaf has a driven original binding owner ancestor')
  if (associatedOverrides.length) reasons.push('Actual original-source ancestor/leaf override prevents admitted native fixed-control eligibility')
  return { path, status: reasons.length ? 'unmeasured' : 'fixed', reasons, originalBindingOwnerPath: original?.bindingOwnerPath ?? null, originalBinding: serializeNativeBinding(original?.binding ?? null), station: original?.station ?? null, nonRigidKinds, dynamicAncestors, associatedOverrides, originalCPUClosureSHA256: inventory?.closureSHA256 ?? null, policy: 'admitted-original9e72-structural-world-motion-dependencies-in-current-source; no continuous-input fixed claim' }
}

async function computedFeatureEligibility(expectedDraw, entries, posedMap, raster, poseOracle) {
  const features = [], binding = expectedDraw.binding, originalInventory = new Map(poseOracle.inventory.drawables.map(entry => [entry.path, entry]))
  for (const witness of expectedDraw.witnesses ?? []) {
    const entry = entries.get(witness.partPath), pose = posedMap.get(witness.partPath)
    if (!entry || !pose) continue
    const fixedEligibility = qualifyOriginalNativeFixedLeaf(witness.partPath, entry, poseOracle.inventory, binding.partOverrides)
    const row = { anchorId: witness.anchorId, partPath: witness.partPath, bindingOwnerPath: pose.bindingOwnerPath, binding: serializeNativeBinding(pose.binding), station: pose.station, effectiveVisibility: pose.effectiveVisibility, motion: 'unknown', status: 'unmeasured', firstSurface: false, firstSurfaceProof: null, restPointMetres: null, posedPointMetres: null, finiteSensitivity: null }
    try {
      const feature = verifyNativeMeshFeatureWitness(witness, entry.primitive), local = posedFeaturePoint(witness, feature, entry, pose.springLengthM, new Float64Array(3))
      row.restPointMetres = new Vector3().fromArray(feature.localPointMetres).applyMatrix4(new Matrix4().fromArray(originalInventory.get(witness.partPath).restMatrixF64)).toArray()
      row.posedPointMetres = new Vector3().fromArray(local).applyMatrix4(new Matrix4().fromArray(pose.matrixWorld)).toArray()
      const support = raster?.witnesses.find(item => item.anchorId === witness.anchorId)
      if (support && !raster.failures.length && !raster.gaps.some(reason => reason.includes(witness.anchorId))) { row.firstSurface = true; row.firstSurfaceProof = support.nearestHit; row.status = 'qualified' }
      if (fixedEligibility.status === 'fixed') row.motion = 'fixed'
      features.push(row)
    } catch (error) { row.reason = error.message; features.push(row) }
  }
  // A body's moving binding does not make its fixed hub/axis a moving feature.
  // Admit moving only after the protected original CPU law moves this actual
  // feature under a finite independently constructed input perturbation.
  const candidates = features.filter(feature => feature.motion === 'unknown' && feature.posedPointMetres)
  if (candidates.length) {
    const probes = [JSON.parse(canonicalJson(binding.input))]
    probes[0].crankTurns += 1 / 64
    const amplitudeProbe = JSON.parse(canonicalJson(binding.input))
    amplitudeProbe.amplitudes = amplitudeProbe.amplitudes.map(value => value === 0 ? 0.0001 : value * 0.99)
    probes.push(amplitudeProbe)
    for (const input of probes) {
      let probe
      try { probe = await poseOracle.solve(input, binding.partOverrides) } catch { continue }
      const map = new Map(probe.drawables.map(entry => [entry.path, entry]))
      for (const candidate of candidates) {
        if (candidate.motion === 'moving') continue
        const witness = expectedDraw.witnesses.find(item => item.anchorId === candidate.anchorId), entry = entries.get(candidate.partPath), pose = map.get(candidate.partPath)
        const feature = verifyNativeMeshFeatureWitness(witness, entry.primitive), local = posedFeaturePoint(witness, feature, entry, pose.springLengthM, new Float64Array(3))
        const point = new Vector3().fromArray(local).applyMatrix4(new Matrix4().fromArray(pose.matrixWorld))
        const displacementMetres = point.distanceTo(new Vector3().fromArray(candidate.posedPointMetres))
        if (displacementMetres > POSITION_BOUND * 2) { candidate.motion = 'moving'; candidate.finiteSensitivity = { inputSHA256: jsonDigest(input), maxWorldDisplacementM: displacementMetres, probeCount: probes.length, policy: 'actual-feature finite original-CPU sensitivity; no continuous-motion claim' } }
      }
    }
  }
  return features
}
function partContains(partPath, path, primitive) {
  return path === partPath || path.startsWith(`${partPath}/`) || !primitive.instanceOf && (primitive.rawPath === partPath || primitive.rawPath.startsWith(`${partPath}/`))
}
function polygonContainsRectangle(polygon, bounds, margin) {
  if (!Array.isArray(polygon) || polygon.length < 3 || !bounds?.every(Number.isFinite)) return false
  const x0 = bounds[0] - margin, y0 = bounds[1] - margin, x1 = bounds[2] + margin, y1 = bounds[3] + margin
  for (let corner = 0; corner < 4; corner++) {
    const x = corner & 1 ? x1 : x0, y = corner & 2 ? y1 : y0
    let inside = false
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const a = polygon[i], b = polygon[j]
      if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside
    }
    if (!inside) return false
  }
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j], dx = b[0] - a[0], dy = b[1] - a[1]
    let lo = 0, hi = 1
    for (let axis = 0; axis < 2; axis++) {
      const start = a[axis], delta = axis ? dy : dx, minimum = axis ? y0 : x0, maximum = axis ? y1 : x1
      if (delta === 0) { if (start <= minimum || start >= maximum) { lo = 1; hi = 0; break } }
      else { const t0 = (minimum - start) / delta, t1 = (maximum - start) / delta; lo = Math.max(lo, Math.min(t0, t1)); hi = Math.min(hi, Math.max(t0, t1)) }
    }
    if (lo <= hi) return false
  }
  return true
}
/** Consume only Node-derived raster support. An assembly's few visible
 * features never stand in for pixel/source eligibility of every claimed leaf.
 * No original coverage kind currently certifies a whole assembly contour by
 * one leaf: unsupported assembly evidence remains explicitly unmeasured. */
export function qualifyNativeSourceVisibleLeaves({ paths, coverage, raster, rigidAttachmentEligible = false }) {
  const gaps = [], members = new Set(paths), ids = coverage?.landmarkIds ?? coverage?.lineCheckIds ?? coverage?.contourCheckIds ?? []
  const isRigid = coverage?.kind === 'rigid-native-attachment'
  const admittedWitnesses = (raster?.witnesses ?? []).filter(row => {
    const footprint = row.footprint, footprintVisible = footprint && (footprint.visibleRimCount > 0 || footprint.visibleCapCount > 0 || new Set(footprint.visibleSlotTriangleIndices ?? []).size >= 2)
    return members.has(row.partPath) && ids.includes(row.anchorId) && row.sourceEvidenceQualified === true && row.nearestHit?.path === row.partPath && row.supportTriangleIndices?.includes(row.nearestHit.triangleIndex)
      && (row.pointIsSurfacePoint === true || footprintVisible) && (!footprint || footprintVisible)
  })
  const admittedContours = (raster?.contours ?? []).filter(row => members.has(row.partPath) && ids.includes(row.id) && row.status === 'qualified' && row.rayCount > 0 && row.nearestHits?.length === row.rayCount && row.nearestHits.every(hit => hit.path === row.partPath))
  if (!isRigid) for (const id of ids) if (!admittedWitnesses.some(row => row.anchorId === id) && !admittedContours.some(row => row.id === id)) gaps.push(`Original source coverage ${id}: genuine current native first-surface support absent`)
  const leaves = paths.map(path => {
    const nativeFirstSurfacePixelCount = raster?.pathPixelCounts?.[path] ?? 0, sourceFeatureIds = admittedWitnesses.filter(row => row.partPath === path).map(row => row.anchorId), sourceContourIds = admittedContours.filter(row => row.partPath === path).map(row => row.id), reasons = []
    if (!(Number.isSafeInteger(nativeFirstSurfacePixelCount) && nativeFirstSurfacePixelCount > 0)) reasons.push('Source-visible leaf has no genuine same-epoch native first-surface pixel; an explicit original descendant exclusion/fixed declaration is required')
    if (!(isRigid && rigidAttachmentEligible) && !sourceFeatureIds.length && !sourceContourIds.length) reasons.push('Source-visible leaf has no independently original-bound current native source support; another leaf/ancestor feature cannot promote it')
    gaps.push(...reasons.map(reason => `${path}: ${reason}`))
    return { path, status: reasons.length ? 'unmeasured' : 'qualified', nativeFirstSurfacePixelCount, sourceFeatureIds, sourceContourIds, sourceSupportPolicy: isRigid && rigidAttachmentEligible ? 'independently-original-bound-rigid-native-attachment' : 'exact-native-leaf-feature-or-contour', reasons }
  })
  return { status: gaps.length ? 'unmeasured' : 'qualified', gaps, leaves, policy: 'every-source-visible-native-leaf-needs-same-epoch-pixels-and-original-source-eligibility; no ancestor/partial-body promotion' }
}

async function proveSourceBodyEligibility(expectedDraw, model, entries, posedMap, raster, numeric, inventory, bindingSHA256) {
  const failures = [], gaps = [], bodyProofs = [], assigned = new Map(), binding = expectedDraw.binding
  const actualCensus = inventory.drawables.map(original => {
    const primitive = model.primitives.get(original.path)
    return { path: original.path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, rawNodeIndex: primitive.nodeIndex, rawMeshIndex: primitive.meshIndex, rawPrimitiveIndex: primitive.primitiveIndex, instanceOf: primitive.instanceOf, bindingOwnerPath: original.bindingOwnerPath, binding: serializeNativeBinding(original.binding), station: original.station }
  })
  let declaredPartCount = 0, sourceNonIdentifiableFixedPartCount = 0
  try {
    if (!expectedDraw.allCurrent462Census) gaps.push('Independent original all-current462 source-body census absent')
    else insist(canonicalJson(expectedDraw.allCurrent462Census) === canonicalJson(actualCensus), 'Independent source-body census differs from actual raw ancestry/original binding/station')
    const data = expectedDraw.sourceOriginalData
    insist(data && Array.isArray(data.frames), 'Original admitted source records absent')
    const frames = data.frames.filter(frame => frame.shotId === binding.shotId && frame.decodedTimeSeconds === binding.decodedTimeSeconds && canonicalJson(frame.sourceImage) === canonicalJson(binding.sourceImage))
    const originalViewId = expectedDraw.sourceView?.originalViewId ?? binding.viewId, views = frames.flatMap(frame => frameViews(frame).filter(view => view.id === originalViewId))
    insist(views.length > 0, 'Original exact decoded-exposure source view absent')
    const sourceState = views[0].mechanicalState ?? null
    insist(views.every(view => canonicalJson(view.mechanicalState ?? null) === canonicalJson(sourceState)), 'Contradictory original source mechanical states')
    const status = sourceState?.status ?? null, runtimeWitness = status === 'constrained' ? sourceState.runtimeWitness ?? null : null
    const proof = status === 'constrained' ? runtimeWitness?.visibilityProof ?? null : status === 'observed' ? sourceState.visibilityProof ?? null : null
    insist(expectedDraw.sourceMechanicalStateStatus === status && canonicalJson(expectedDraw.sourceRuntimeWitness ?? null) === canonicalJson(runtimeWitness) && canonicalJson(expectedDraw.sourceVisibilityProof ?? null) === canonicalJson(proof), 'Caller source proof differs from actual original selected source record')
    const expected = expectedDraw.expectedVisibilityBinding
    insist(expected && expected.modelSha256 === model.rawSHA256 && expected.modelSourceCommit === binding.modelSourceCommit, 'Independent source visibility binding absent/different actual model')
    for (const key of ['sourceVideoId', 'sourceSha256', 'sourceImage', 'shotId', 'viewId', 'timeSeconds', 'decodedTimeSeconds', 'input', 'rectSourcePixels', 'presentation', 'imagePlaneWarp', 'resolvedImagePlaneWarp', 'sourceLayout', 'composite', 'partOverrides']) insist(canonicalJson(expected[key]) === canonicalJson(binding[key]), `Independent source body binding differs: ${key}`)
    const logical = binding.resolvedImagePlaneWarp?.unwarpedViewportPixels ?? binding.rectSourcePixels.slice(2)
    const normalizedCamera = camera => {
      const snapshot = nativeExpectedCameraSnapshot(camera, logical)
      return { ...snapshot, principalPointViewportPixels: snapshot.principalPointViewportPixels ?? [logical[0] / 2, logical[1] / 2] }
    }
    const { quaternion: sourceQuaternion, ...sourceCamera } = normalizedCamera(expected.camera), { quaternion: boundQuaternion, ...boundCamera } = normalizedCamera(binding.camera)
    const sameOrientation = sourceQuaternion.every((value, i) => Math.abs(value - boundQuaternion[i]) <= 1e-7) || sourceQuaternion.every((value, i) => Math.abs(value + boundQuaternion[i]) <= 1e-7)
    insist(canonicalJson(sourceCamera) === canonicalJson(boundCamera) && sameOrientation, 'Original source body camera is not the independently bound logical camera')
    insist(canonicalJson(expected.nativeGeometryAssumptions) === canonicalJson(data.nativeGeometryAssumptions ?? []) && canonicalJson(expected.constraints) === canonicalJson(runtimeWitness?.constraints ?? []) && canonicalJson(expected.continuity) === canonicalJson(runtimeWitness?.continuity ?? null) && canonicalJson(expected.sourceNonIdentifiableFixedParts) === canonicalJson(proof?.sourceNonIdentifiableFixedParts ?? []), 'Source body constraints/assumptions differ from actual original records')
    const landmarks = frames.flatMap(frame => (frame.landmarks ?? []).filter(row => (row.viewId ?? 'main') === originalViewId))
    gaps.push(...(status === 'constrained' ? witnessErrors(runtimeWitness, expected, data.anchors ?? [], landmarks, views[0]) : visibilityProofErrors(proof, expected, data.anchors ?? [], landmarks, views[0])))
    if (!['observed', 'constrained'].includes(status)) gaps.push('Original source has no admitted observed/constrained complete physical body proof')
    for (const override of binding.partOverrides) if (override.worldPositionMetres || override.worldQuaternion || override.visibility === 'hidden') {
      insist(typeof override.evidence === 'string' && override.evidence.trim() && override.sourceTimeSeconds === binding.decodedTimeSeconds && Array.isArray(override.landmarkIds) && override.landmarkIds.length && new Set(override.landmarkIds).size === override.landmarkIds.length && override.landmarkIds.every(id => landmarks.some(row => row.anchorId === id && row.status === 'observed' && row.role === 'check')), 'Source disassembly override lacks exact-exposure original CHECK support')
    }
    const declarations = [...(proof?.sourceVisibleParts ?? []).map(row => ({ path: row.partPath, scope: 'source-visible', row })), ...(proof?.excludedParts ?? []).map(row => ({ path: row.partPath, scope: 'source-excluded', row })), ...(proof?.sourceNonIdentifiableFixedParts ?? []).map(row => ({ path: row.nativePartPath, scope: 'source-non-identifiable-fixed', row }))]
    declaredPartCount = declarations.length; sourceNonIdentifiableFixedPartCount = proof?.sourceNonIdentifiableFixedParts?.length ?? 0
    const validPaths = new Set([...model.nodes.keys(), ...inventory.drawables.map(row => row.path)]), declaredPaths = new Set()
    for (const declaration of declarations) { insist(validPaths.has(declaration.path) && !declaredPaths.has(declaration.path), 'Source body declaration has foreign/duplicate actual native path'); declaredPaths.add(declaration.path) }
    for (const [path, entry] of entries) {
      const matches = declarations.filter(row => partContains(row.path, path, entry.primitive)).sort((a, b) => b.path.length - a.path.length)
      if (!matches.length) { gaps.push(`${path}: original full-source body census membership absent`); continue }
      const members = assigned.get(matches[0].path) ?? []; members.push(path); assigned.set(matches[0].path, members)
    }
    for (const declaration of declarations) {
      const paths = assigned.get(declaration.path) ?? [], row = declaration.row, record = { partPath: declaration.path, scope: declaration.scope, status: 'qualified', drawablePaths: paths, nativeFirstSurfacePixelCount: paths.reduce((sum, path) => sum + (raster?.pathPixelCounts?.[path] ?? 0), 0) }
      const reject = reason => { record.status = 'unmeasured'; record.reason = reason; gaps.push(`${declaration.path}: ${reason}`) }
      if (!paths.length) reject('Declared source body has no authentic current native drawable membership')
      if (declaration.scope === 'source-visible') {
        const coverage = row.sourceCoverage
        let rigidAttachmentEligible = false
        if (coverage?.kind === 'rigid-native-attachment') {
          const parent = declarations.find(item => item.path === coverage.attachedToPartPath && item.scope === 'source-visible'), parentPaths = parent ? [...entries].filter(([path, entry]) => partContains(parent.path, path, entry.primitive)).map(([path]) => path) : []
          const owners = new Set(parentPaths.map(path => canonicalJson({ owner: posedMap.get(path).bindingOwnerPath, binding: serializeNativeBinding(posedMap.get(path).binding), station: posedMap.get(path).station })))
          rigidAttachmentEligible = owners.size === 1 && paths.every(path => owners.has(canonicalJson({ owner: posedMap.get(path).bindingOwnerPath, binding: serializeNativeBinding(posedMap.get(path).binding), station: posedMap.get(path).station })))
          if (!rigidAttachmentEligible) reject('Native attachment is not independently rigid under the same original binding/station')
        }
        const leafEligibility = qualifyNativeSourceVisibleLeaves({ paths, coverage, raster, rigidAttachmentEligible })
        record.leafEligibility = leafEligibility.leaves
        for (const reason of leafEligibility.gaps) reject(reason)
      } else if (declaration.scope === 'source-non-identifiable-fixed') {
        record.leafEligibility = paths.map(path => qualifyOriginalNativeFixedLeaf(path, entries.get(path), inventory, binding.partOverrides))
        for (const leaf of record.leafEligibility) for (const reason of leaf.reasons) reject(`${leaf.path}: ${reason}`)
      } else if (row.reason === 'absent') {
        if (paths.some(path => posedMap.get(path).effectiveVisibility !== 'hidden')) reject('Source-absent body is not actually absent in the independently solved native view')
      } else {
        const domains = paths.flatMap(path => numeric.filter(item => item.path === path && item.family === 'nativeID').flatMap(item => item.cameraProof?.domains ?? []))
        if (!domains.length) reject('Source exclusion lacks current independently enclosed authentic native triangle support')
        else if (row.reason === 'outside') {
          if (record.nativeFirstSurfacePixelCount || domains.some(domain => !['proved-outside-homogeneous-clip-volume', 'outside-source-support'].includes(domain.status))) reject('Source-outside body has unresolved/inside current native support')
        } else if (row.reason === 'occluded') {
          if (record.nativeFirstSurfacePixelCount || !domains.some(domain => domain.source && !domain.status.startsWith('ambiguous-')) || domains.some(domain => domain.status.startsWith('ambiguous-'))) reject('Source-occluded body is not completely excluded by genuine same-epoch first-surface raster/support')
        } else if (row.reason === 'source-occluded') {
          const mask = row.sourceOcclusion
          if (domains.some(domain => domain.status.startsWith('ambiguous-') || domain.source && !polygonContainsRectangle(mask?.polygonSourcePixels, [domain.source[0][0], domain.source[1][0], domain.source[0][1], domain.source[1][1]], mask.uncertaintyPx))) reject('Required native body footprint is not independently contained inside the original measured opaque source mask')
        } else reject('Unsupported original source body exclusion')
      }
      bodyProofs.push(record)
    }
  } catch (error) {
    if (/absent|missing|no admitted/.test(error.message)) gaps.push(error.message)
    else failures.push(error.message)
  }
  const coveredNativeDrawableCount = [...assigned.values()].reduce((sum, paths) => sum + paths.length, 0)
  if (coveredNativeDrawableCount !== 462) gaps.push(`Original full-source proof covers ${coveredNativeDrawableCount}/462 authentic native drawables`)
  return { status: failures.length ? 'failed' : gaps.length ? 'unmeasured' : 'qualified', failures, gaps, bindingSHA256, nativeDrawableCount: actualCensus.length, rawPrimitiveCount: new Set(actualCensus.map(row => `${row.rawNodeIndex}/${row.rawMeshIndex}/${row.rawPrimitiveIndex}`)).size, rawNamedNodeCount: model.nodes.size, springDrawableCount: [...entries.values()].filter(entry => entry.springOracle).length, springVertexCount: [...entries.values()].filter(entry => entry.springOracle).reduce((sum, entry) => sum + entry.primitive.positions.length / 3, 0), declaredPartCount, coveredNativeDrawableCount, sourceNonIdentifiableFixedPartCount, bodyProofs, censusSHA256: jsonDigest(actualCensus), completedSceneDrawEpoch: binding.completedSceneDrawEpoch, policy: 'existing-original-source-validator-plus-independent-complete-current462-raw-pose-first-surface-census; no partial-body promotion' }
}

/** Only results minted here are authorized; receipt pass/status/max never enter. */
export async function createNativeQualificationSession({ byteStore, rawGLBBytes, deliveryGLBBytes, codeClosure, poseOracle, originalSpringOraclePath, originalSpringOracleSHA256 }) {
  insist(byteStore?.get && poseOracle?.solve && poseOracle?.inventory, 'Actual bytes and independently frozen CPU oracle required')
  const model = await proveCurrentNativeModelBytes(rawGLBBytes, deliveryGLBBytes), codeManifest = closeNativeCodeManifest(codeClosure)
  insist(poseOracle.inventory.rawSHA256 === model.rawSHA256 && poseOracle.inventory.deliverySHA256 === model.deliverySHA256 && poseOracle.inventory.closureSHA256 === codeClosure.originalSceneClosureSHA256, 'CPU pose oracle closure/model not independently pinned')
  model.primitives = bindNativeRawPrimitivesToOriginalInventory(model, poseOracle.inventory)
  const materialProof = await createNativeMaterialProof({ rawGLBBytes, deliveryGLBBytes, model })
  const oracleBytes = await readFile(originalSpringOraclePath), oracleHash = sha256(oracleBytes)
  const approvedOracleSHA256 = 'e84fd4318890130e8183ebdcce1560796b24b6e0b4ac3e15b890545c8dd9a5fa'
  requireSHA(originalSpringOracleSHA256, 'original oracle pinned SHA')
  insist(typeof originalSpringOraclePath === 'string' && originalSpringOraclePath.endsWith('/original-f64-oracle-sealed-20261003.mjs') && originalSpringOracleSHA256 === approvedOracleSHA256 && oracleHash === approvedOracleSHA256, 'Explicit approved sealed original F64 oracle path/hash required')
  const protectedBytes = await readFile(new URL('../.vite/verification-output/native-v39-spring-baseline-20261003/original-f64-oracle-sealed-20261003.mjs', import.meta.url))
  insist(sha256(protectedBytes) === approvedOracleSHA256 && bytesEqual(protectedBytes, oracleBytes), 'Supplied oracle differs from independently pinned immutable sealed original')
  const originalOracle = await import(`data:text/javascript;base64,${oracleBytes.toString('base64')}`)
  insist(typeof originalOracle.createOriginalSpringOracle === 'function', 'Original immutable oracle API absent')
  const authorized = new WeakSet(), staticCache = new Map(), geometryCache = new Map(), bvhCache = new Map(), epochs = new Map(), quadGeometry = new PlaneGeometry(2, 2)
  let disposed = false, queue = Promise.resolve()
  async function qualifyDraw(receipt, expectedDraw) {
    const failures = [], gaps = [], numeric = [], nativePhysicalCacheKeys = [], reader = createNativeByteReader(byteStore)
    let raster = null, bindingSHA256 = null, features = [], sourceBodyEligibility = { status: 'unmeasured', failures: [], gaps: ['Independent complete native/source body proof not reached'], nativeDrawableCount: 462, coveredNativeDrawableCount: 0 }
    try {
      insist(!disposed, 'Qualification session disposed')
      requireClosed(receipt, ['schemaVersion', 'binding', 'staticNativeSHA256', 'drawableStateSHA256', 'submitted', 'presentationSubmissions', 'numericOutputs', 'raster', 'rawCaseRetention'], 'receipt')
      requireClosed(receipt.binding, bindingKeys, 'binding'); requireClosed(expectedDraw.binding, bindingKeys, 'independent expected binding')
      insist(receipt.schemaVersion === 1 && ['retained-selected-case', 'streamed-live-only'].includes(receipt.rawCaseRetention), 'Unsupported receipt version/retention')
      insist(canonicalJson(receipt.binding) === canonicalJson(expectedDraw.binding), 'Receipt source/input/view/epoch tuple differs from independently supplied expectation')
      const binding = expectedDraw.binding
      insist(binding.modelRawSHA256 === CURRENT_NATIVE_RAW_SHA256 && binding.modelDeliverySHA256 === CURRENT_NATIVE_DELIVERY_SHA256 && binding.modelDeliveryByteLength === CURRENT_NATIVE_DELIVERY_BYTES && binding.currentBuildClosureSHA256 === codeClosure.sha256 && binding.inputSHA256 === jsonDigest(binding.input), 'Independent binding not closed against actual model/code/input bytes')
      for (const name of ['decodedFrameIndex', 'sourceDrawRevision', 'completedSceneDrawEpoch']) integer(binding[name], name)
      insist(binding.completedSceneDrawEpoch > 0 && binding.sourceDrawRevision > 0, 'Completed scene epoch/revision absent')
      const epochKey = `${binding.sourceVideoId}/${binding.viewId}`, prior = epochs.get(epochKey)
      insist(!prior || binding.completedSceneDrawEpoch >= prior.epoch, 'Stale completed scene epoch')
      bindingSHA256 = jsonDigest(binding)
      if (prior?.epoch === binding.completedSceneDrawEpoch) insist(prior.bindingSHA256 === bindingSHA256, 'One scene epoch rebound to a different input/source/camera')
      const staticManifest = await reader.json(receipt.staticNativeSHA256)
      let entries = staticCache.get(receipt.staticNativeSHA256)
      if (!entries) { entries = await proveStatic(reader, staticManifest, model, poseOracle, codeManifest, originalOracle.createOriginalSpringOracle); staticCache.set(receipt.staticNativeSHA256, entries) }
      const posed = await poseOracle.solve(binding.input, binding.partOverrides), posedMap = new Map(posed.drawables.map(entry => [entry.path, entry]))
      insist(posedMap.size === 462 && posed.drawables.length === 462, 'Independent posed inventory incomplete')
      const state = await reader.json(receipt.drawableStateSHA256)
      insist(Array.isArray(state) && state.length === 462, 'Actual full462 scene-state bytes absent')
      const paths = [...entries.keys()]
      for (let i = 0; i < state.length; i++) {
        const row = state[i]; requireClosed(row, ['path', 'matrixWorldF64', 'effectiveVisibility', 'groups', 'drawRange', 'materialSlotsSHA256', 'bindingOwnerPath', 'binding', 'station', 'springLengthM'], 'drawable state')
        const independent = posedMap.get(row.path)
        insist(row.path === paths[i] && independent && row.effectiveVisibility === independent.effectiveVisibility, 'Ordered full inventory/visibility differs from original pose')
        for (const key of ['bindingOwnerPath', 'binding', 'station', 'springLengthM']) insist(canonicalJson(row[key]) === canonicalJson(key === 'binding' ? serializeNativeBinding(independent[key]) : independent[key]), `Actual ${key} differs from independent original pose`)
        requireClosed(row.drawRange, ['start', 'count'], 'actual scene draw range')
        integer(row.drawRange.start, 'scene draw range start'); integer(row.drawRange.count, 'scene draw range count')
        insist(row.drawRange.start + row.drawRange.count <= entries.get(row.path).primitive.index.length, 'Actual scene draw range exceeds full raw index bytes')
        insist(numbersEqual(await reader.numbers(row.matrixWorldF64, { scalar: 'f64le', components: 16, count: 1 }), independent.matrixWorld), 'Actual hidden/visible drawable matrix differs')
        for (const hash of row.materialSlotsSHA256) requireSHA(hash, 'actual material slot')
        for (const group of row.groups) { requireClosed(group, ['start', 'count', 'materialIndex'], 'geometry group'); integer(group.start, 'group start'); integer(group.count, 'group count'); integer(group.materialIndex, 'material index'); insist(group.start + group.count <= entries.get(row.path).primitive.index.length && group.materialIndex < row.materialSlotsSHA256.length, 'Geometry group/material bounds differ') }
        const original = poseOracle.inventory.drawables[i], originalRange = original.geometry.drawRange
        insist(canonicalJson(row.groups) === canonicalJson(original.geometry.groups.map(group => ({ start: group.start, count: group.count, materialIndex: group.materialIndex ?? 0 }))) && canonicalJson(row.drawRange) === canonicalJson({ start: originalRange.start, count: Math.max(0, Math.min(originalRange.count, entries.get(row.path).primitive.index.length - originalRange.start)) }), 'Actual original geometry groups/draw range changed')
        insist(row.materialSlotsSHA256.length === (Array.isArray(original.object.material) ? original.object.material.length : 1), 'Actual original material slot census differs')
      }
      const camera = cameraMatrices(binding, receipt.raster.nativePathID.width, receipt.raster.nativePathID.height, poseOracle.inventory.cameraNearFar), submittedKeys = new Set(), outputMap = new Map(), usedOutputs = new Set(), coveredRanges = new Map(), cameraBounds = new Map(), geometryBounds = new Map(), measuredSpringPaths = new Set()
      const rasterGeometry = await closePresentationSubmissions(reader, receipt.presentationSubmissions, binding, expectedDraw.rasterGeometry, quadGeometry)
      for (const output of receipt.numericOutputs) { const key = `${output.path}/${output.family}/${output.geometryStateSHA256}`, batches = outputMap.get(key) ?? []; batches.push(output); outputMap.set(key, batches) }
      for (const submitted of receipt.submitted) {
        const entry = entries.get(submitted.path), independent = posedMap.get(submitted.path)
        insist(entry && independent, 'Foreign submitted native primitive')
        const closed = await proveSubmitted(reader, submitted, entry, independent, camera), outputKey = `${submitted.path}/${submitted.family}/${closed.key}`
        closed.fullKey = nativeSubmissionStateSHA256(submitted)
        insist(!submittedKeys.has(closed.fullKey), 'Duplicate complete actual submitted state'); submittedKeys.add(closed.fullKey)
        const coverageKey = `${submitted.path}/${submitted.family}`, ranges = coveredRanges.get(coverageKey) ?? []
        ranges.push(submitted.drawRange); coveredRanges.set(coverageKey, ranges)
        const outputs = (outputMap.get(outputKey) ?? []).filter(output => output.submissionStateSHA256 === null || output.submissionStateSHA256 === closed.fullKey)
        for (const output of outputs) usedOutputs.add(output)
        const coreBatches = outputs.filter(output => output.submissionStateSHA256 === null), cameraBatches = outputs.filter(output => output.submissionStateSHA256 !== null)
        const descriptorSHA256 = jsonDigest(physicalOutputDescriptor(coreBatches)), poseSHA256 = jsonDigest({ matrix: Array.from(independent.matrixWorld), springLengthM: independent.springLengthM }), cached = geometryCache.get(closed.key)
        const hit = cached && cached.descriptorSHA256 === descriptorSHA256 && cached.poseSHA256 === poseSHA256
        const coreProof = hit ? cached.proof : await proveNumeric(reader, coreBatches, submitted, closed, entry, independent)
        if (!coreProof.gaps.length && !coreProof.failures.length) {
          if (!hit) { geometryCache.set(closed.key, { descriptorSHA256, poseSHA256, proof: coreProof }); if (!cached) nativePhysicalCacheKeys.push(closed.key) }
          if (entry.springOracle) measuredSpringPaths.add(submitted.path)
        }
        if (coreProof.cameraDomain?.localBoundsF64) geometryBounds.set(submitted.path, coreProof.cameraDomain.localBoundsF64)
        const freshCamera = coreProof.gaps.length || coreProof.failures.length ? { gaps: [], failures: [], fields: {}, cameraProof: { domainStatus: 'unmeasured-physical-prerequisite', measuredCameraTF: false } } : qualifyNativeCameraEnclosure({ coreProof, submitted, closed, staticEntry: entry, posed: independent, expectedView: { binding, cameraNearFar: poseOracle.inventory.cameraNearFar, cameraMatrices: { world: camera.world.elements, view: camera.view.elements, projection: camera.projection.elements }, rasterGeometry, cameraSupports: expectedDraw.cameraSupports ?? [] } })
        const selectedCamera = await proveSelectedCamera(reader, cameraBatches, submitted, closed, entry, independent, freshCamera)
        const proof = { ...coreProof, fields: { ...coreProof.fields, ...freshCamera.fields }, cameraProof: freshCamera.cameraProof, selectedCamera, geometryCacheHit: Boolean(hit), gaps: [...coreProof.gaps, ...freshCamera.gaps, ...(selectedCamera?.gaps ?? [])], failures: [...coreProof.failures, ...freshCamera.failures, ...(selectedCamera?.failures ?? [])] }
        const componentBounds = freshCamera.cameraProof.componentErrorBounds
        if (componentBounds?.view?.length === 3 && componentBounds?.clip?.length === 4 && [...componentBounds.view, ...componentBounds.clip].every(value => Number.isFinite(value) && value >= 0)) {
          const prior = cameraBounds.get(submitted.path)
          cameraBounds.set(submitted.path, {
            viewPositionBound: componentBounds.view.map((value, axis) => Math.max(prior?.viewPositionBound[axis] ?? 0, value)),
            clipErrorBound: componentBounds.clip.map((value, axis) => Math.max(prior?.clipErrorBound[axis] ?? 0, value)),
          })
        }
        numeric.push({ path: submitted.path, family: submitted.family, stateSHA256: closed.key, submissionStateSHA256: closed.fullKey, ...proof }); gaps.push(...proof.gaps); failures.push(...proof.failures)
      }
      for (const [path, entry] of entries) {
        if (entry.springOracle && !measuredSpringPaths.has(path)) gaps.push(`${path}: current required full-stock physical state bytes absent`)
        const pose = posedMap.get(path)
        if (pose.effectiveVisibility !== 'visible') continue
        for (const family of ['standard', 'nativeID']) {
          const ranges = (coveredRanges.get(`${path}/${family}`) ?? []).sort((a, b) => a.start - b.start)
          let cursor = 0; for (const range of ranges) { if (range.start > cursor) break; cursor = Math.max(cursor, range.start + range.count) }
          if (cursor !== entry.primitive.index.length) gaps.push(`${path}/${family}: full authentic submitted index coverage absent`)
        }
      }
      for (const output of receipt.numericOutputs) insist(usedOutputs.has(output), 'Numeric output without its actual complete submitted program/input state')
      raster = await proveRaster(reader, receipt, expectedDraw, entries, posedMap, camera, bvhCache, materialProof, state, cameraBounds, geometryBounds); gaps.push(...raster.gaps); failures.push(...raster.failures)
      sourceBodyEligibility = await proveSourceBodyEligibility(expectedDraw, model, entries, posedMap, raster, numeric, poseOracle.inventory, bindingSHA256)
      features = await computedFeatureEligibility(expectedDraw, entries, posedMap, raster, poseOracle)
      epochs.set(epochKey, { epoch: binding.completedSceneDrawEpoch, bindingSHA256 })
    } catch (error) {
      if (/missing|absent|unavailable|Unsupported|unsupported|Uncaptured/.test(error.message)) gaps.push(error.message)
      else failures.push(error.message)
    }
    const retention = expectedDraw?.rawCaseRetention === 'retained-selected-case' ? 'retained-selected-case' : 'streamed-live-only'
    const result = freezeComputed({ schemaVersion: 1, status: failures.length ? 'failed' : gaps.length ? 'unmeasured' : 'qualified', failures, gaps, bindingSHA256, modelRawSHA256: model.rawSHA256, modelDeliverySHA256: model.deliverySHA256, codeClosureSHA256: codeClosure.sha256, originalSpringOracleSHA256: oracleHash, numeric, raster, features, sourceBodyEligibility, nativePhysicalCacheKeys, rawCaseRetention: retention, revalidationScope: retention === 'retained-selected-case' ? 'retained-selected-case' : 'streamed-live-only; no offline-all-output revalidation claim' })
    authorized.add(result)
    return result
  }
  function scheduleDraw(receipt, expectedDraw) {
    const result = queue.then(() => qualifyDraw(receipt, expectedDraw))
    queue = result.then(() => undefined, () => undefined)
    return result
  }
  return { qualifyDraw: scheduleDraw, isAdjudication: result => authorized.has(result), dispose() { disposed = true; staticCache.clear(); geometryCache.clear(); bvhCache.clear(); epochs.clear(); quadGeometry.dispose() } }
}
