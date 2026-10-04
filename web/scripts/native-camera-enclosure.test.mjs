import test from 'node:test'
import assert from 'node:assert/strict'
import { Matrix3, Matrix4, PerspectiveCamera } from 'three'
import { createNativeCameraDomainSummary, encloseNativeCameraPoint, encloseNativeViewClipPoint, nativeCameraShaderProfile, prepareNativeMirrorSubmission, prepareNativeWarpSubmission, qualifyNativeCameraEnclosure, validateNativeCameraSamples } from './native-camera-enclosure.mjs'

// Parent executes this scoped suite. It tests numerical/domain behavior, not
// copied source text, producer statuses, or final-output-derived tolerances.
const shader = `#version 300 es
precision highp float;
uniform mat4 modelViewMatrix;
uniform mat4 projectionMatrix;
uniform mat3 normalMatrix;
in vec3 position;
in vec3 normal;
out vec3 vNormal;
void main() {
  vec3 objectNormal = vec3(normal);
  vec3 transformedNormal = objectNormal;
  transformedNormal = normalMatrix * transformedNormal;
  vNormal = normalize(transformedNormal);
  vec3 transformed = vec3(position);
  vec4 mvPosition = vec4(transformed, 1.0);
  mvPosition = modelViewMatrix * mvPosition;
  gl_Position = projectionMatrix * mvPosition;
}`
const presentationVertex = `#version 300 es
precision highp float;
in vec3 position;
in vec2 uv;
out vec2 imageUv;
void main() { imageUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }`
const mirrorFragment = `#version 300 es
precision highp float;
uniform sampler2D image;
in vec2 imageUv;
out vec4 colour;
#define gl_FragColor colour
void main() { gl_FragColor=texture2D(image,vec2(1.0-imageUv.x,imageUv.y)); }`
const warpShader = `#version 300 es
precision highp float;
uniform sampler2D image;
uniform mat3 inverseH;
uniform vec2 grid;
uniform vec4 sourceFromBacking;
uniform vec4 rect;
uniform bool warped;
uniform bool mask;
out vec4 colour;
#define gl_FragColor colour
void main() {
  vec2 source = gl_FragCoord.xy * sourceFromBacking.xy + sourceFromBacking.zw;
  if (any(lessThan(source, rect.xy)) || any(greaterThanEqual(source, rect.xy + rect.zw))) discard;
  vec3 local = inverseH * vec3(source, 1.0);
  vec2 p = warped ? local.xy / local.z : source - rect.xy;
  vec2 dimensions = warped ? grid : rect.zw;
  if (any(lessThan(p, vec2(0.0))) || any(greaterThanEqual(p, dimensions))) discard;
  if (mask) { gl_FragColor = vec4(0.0); return; }
  gl_FragColor = texture2D(image, vec2(p.x / dimensions.x, 1.0 - p.y / dimensions.y));
}`
function summary(count) { return { vertexCount: count, comparedComponentCount: count * 3, nonfiniteCount: 0, outsideCount: 0, maxAbsoluteError: 0, maxEuclideanError: 0, maxAngularErrorRadians: 0, maxLengthError: 0, maxEnclosureEuclideanBound: 0 } }
function fixture({ positions = [-0.01, -0.01, 0, 0.01, -0.01, 0, 0, 0.01, 0], cameraPosition = [0, 0, 1], normalError = 0 } = {}) {
  const local = Float32Array.from(positions), count = local.length / 3, indices = Uint32Array.from({ length: count }, (_, i) => i), bounds = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]
  for (let i = 0; i < count; i++) for (let axis = 0; axis < 3; axis++) { bounds[axis] = Math.min(bounds[axis], local[i * 3 + axis]); bounds[axis + 3] = Math.max(bounds[axis + 3], local[i * 3 + axis]) }
  const binding = { viewId: 'native-view', rectSourcePixels: [0, 0, 640, 480], presentation: 'native', composite: null, resolvedImagePlaneWarp: null, camera: { positionMetres: cameraPosition, quaternion: [0, 0, 0, 1], verticalFovDegrees: 45 }, sourceLayout: [{ viewId: 'native-view', rectSourcePixels: [0, 0, 640, 480], composite: null }] }
  const camera = new PerspectiveCamera(45, 640 / 480, 0.005, 100)
  camera.position.fromArray(cameraPosition); camera.updateProjectionMatrix(); camera.updateMatrixWorld(true)
  const posed = { matrixWorld: new Matrix4().elements }, view = camera.matrixWorldInverse.elements, projection = camera.projectionMatrix.elements, normalMatrix = new Matrix3().getNormalMatrix(camera.matrixWorldInverse).elements
  const uniforms = new Map([['modelViewMatrix', Float32Array.from(view)], ['projectionMatrix', Float32Array.from(projection)], ['normalMatrix', Float32Array.from(normalMatrix)]])
  const drawRange = { start: 0, count, mode: 4 }, domain = createNativeCameraDomainSummary({ localActual: { actual: local, stride: 3, offset: 0, components: 3 }, indices, drawRange, localMaxComponentError: [0, 0, 0], localBoundsF64: bounds, objectNormalMinOriginalLength: 1, objectNormalMaxOriginalLength: 1, objectNormalMaxActualLength: 1, objectNormalMaxEuclideanErrorBound: normalError, vertexCount: count })
  const rasterGeometry = { nativeViewportBackingPixels: [0, 0, 640, 480], destinationViewportBackingPixels: [0, 0, 640, 480], destinationScissorBackingPixels: [0, 0, 640, 480], destinationCellSourcePixels: [1, 1], sourceGateBackingPixels: [0, 0, 640, 480], drawingBufferHeight: 480 }
  const geometryStateSHA256 = 'a'.repeat(64), originalProgramSHA256 = 'b'.repeat(64)
  return {
    local, count,
    coreProof: { gaps: [], failures: [], vertexCount: count, geometryStateSHA256, originalProgramSHA256, fields: { local: summary(count), objectNormal: summary(count) }, cameraDomain: domain },
    submitted: { path: 'actual-triangle', family: 'standard', drawRange },
    closed: { key: geometryStateSHA256, programSHA256: originalProgramSHA256, vertexShader: shader, fragmentShader: '', world: posed.matrixWorld, view, projection, uniforms, normalsNeeded: true, worldNeeded: false },
    staticEntry: { springOracle: null }, posed,
    expectedView: { binding, cameraNearFar: [0.005, 100], cameraMatrices: { world: camera.matrixWorld, view: camera.matrixWorldInverse, projection: camera.projectionMatrix }, rasterGeometry },
  }
}
function dotF32(matrix, vector, rows) {
  return Array.from({ length: rows }, (_, row) => {
    let sum = 0
    for (let column = 0; column < rows; column++) sum = Math.fround(sum + Math.fround(matrix[row + rows * column] * vector[column]))
    return sum
  })
}
function samples(f) {
  const normals = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  return Array.from({ length: f.count }, (_, index) => {
    const originalLocal = Array.from(f.local.subarray(index * 3, index * 3 + 3)), originalObjectNormal = normals[index % 3], view = dotF32(f.closed.uniforms.get('modelViewMatrix'), [...originalLocal, 1], 4), clip = dotF32(f.closed.uniforms.get('projectionMatrix'), view, 4), transformed = dotF32(f.closed.uniforms.get('normalMatrix'), originalObjectNormal, 3), length = Math.fround(Math.hypot(...transformed))
    return { originalLocal, originalObjectNormal, view: view.slice(0, 3), clip, viewNormal: transformed.map(value => Math.fround(value / length)) }
  })
}
function installWarp(f, matrix = [1, 0, 0, 0, 1, 0, 0, 0, 1]) {
  const binding = f.expectedView.binding
  binding.resolvedImagePlaneWarp = { kind: 'homography', unwarpedViewportPixels: [640, 480], renderToSourcePixels: matrix }
  f.expectedView.rasterGeometry.warpSubmission = { vertexShader: presentationVertex, fragmentShader: warpShader, uniforms: new Map([['image', Uint32Array.of(0)], ['inverseH', Float32Array.from(new Matrix3().set(...matrix).invert().elements)], ['grid', Float32Array.from([640, 480])], ['sourceFromBacking', Float32Array.from([1, -1, 0, 480])], ['rect', Float32Array.from([0, 0, 640, 480])], ['warped', Uint32Array.of(1)], ['mask', Uint32Array.of(0)]]) }
}

test('unfused Float32 camera outputs fit prior enclosures; all components of view/clip/normal are checked', () => {
  const f = fixture(), proof = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(proof.failures, [])
  assert.deepEqual(proof.gaps, [])
  assert.ok(proof.cameraProof.maxPixelBound > 0 && proof.cameraProof.maxPixelBound < 0.5)
  assert.equal(proof.cameraProof.independentPositionLimitMetres, 1e-7)
  assert.equal(proof.cameraProof.measuredCameraTF, false)
  const measured = validateNativeCameraSamples(proof, samples(f))
  assert.equal(measured.allComponentsInside, true)
  assert.equal(measured.fields.clip.comparedComponentCount, 12)
  assert.equal(measured.fields.viewNormal.comparedComponentCount, 9)
})

test('normalize encloses the specification length-reciprocal and component-division path', () => {
  const f = fixture(), world = new Matrix4().makeScale(2, 3, 4), view = new Matrix4().multiplyMatrices(f.expectedView.cameraMatrices.view, world), normal = new Matrix3().getNormalMatrix(view)
  f.posed.matrixWorld = world.elements; f.closed.world = world.elements; f.closed.view = view.elements
  f.closed.uniforms.set('modelViewMatrix', Float32Array.from(view.elements)); f.closed.uniforms.set('normalMatrix', Float32Array.from(normal.elements))
  f.coreProof.cameraDomain = { ...f.coreProof.cameraDomain, objectNormalMinOriginalLength: Math.sqrt(3), objectNormalMaxOriginalLength: Math.sqrt(3), objectNormalMaxActualLength: Math.sqrt(3) }
  const proof = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(proof.failures, []); assert.deepEqual(proof.gaps, [])
  const shiftTwoULP = value => Math.fround(value + 2 * 2 ** (Math.floor(Math.log2(Math.abs(value))) - 23))
  const values = samples(f)
  for (const sample of values) {
    sample.originalObjectNormal = [1, 1, 1]
    const transformed = dotF32(f.closed.uniforms.get('normalMatrix'), sample.originalObjectNormal, 3)
    const squared = dotF32(Float32Array.from([transformed[0], 0, 0, transformed[1], 0, 0, transformed[2], 0, 0]), transformed, 3)[0]
    const inverseSqrt = shiftTwoULP(Math.fround(1 / Math.sqrt(squared))), length = shiftTwoULP(Math.fround(1 / inverseSqrt))
    sample.viewNormal = transformed.map(value => shiftTwoULP(Math.fround(value / length)))
  }
  assert.equal(validateNativeCameraSamples(proof, values).allComponentsInside, true)
})

test('a fresh camera cannot reuse the previous camera F64 or uploaded matrix tuple', () => {
  const a = fixture(), b = fixture({ cameraPosition: [0.25, 0, 1] })
  assert.deepEqual(qualifyNativeCameraEnclosure(b).failures, [])
  const stale = { ...b, closed: a.closed }
  assert.match(qualifyNativeCameraEnclosure(stale).failures.join('\n'), /Fresh actual submitted view F64/)
  b.closed.uniforms.set('modelViewMatrix', a.closed.uniforms.get('modelViewMatrix'))
  assert.match(qualifyNativeCameraEnclosure(b).failures.join('\n'), /Fresh actual uploaded modelViewMatrix/)
})

test('wrong matrix, NaN, zero W, and wrong final normal cannot widen a previously constructed enclosure', () => {
  const f = fixture(), proof = qualifyNativeCameraEnclosure(f), values = samples(f)
  for (const [name, axis, value] of [['view', 1, 0.5], ['clip', 2, NaN], ['clip', 3, 0], ['viewNormal', 0, 0.5]]) {
    const changed = structuredClone(values); changed[0][name][axis] = value
    const result = validateNativeCameraSamples(proof, changed)
    assert.equal(result.allComponentsInside, false, `${name}/${axis}`)
    assert.ok(result.failures.some(reason => reason.includes(name) || reason.includes('homogeneous W')))
  }
  const uploaded = f.closed.uniforms.get('projectionMatrix'); uploaded[0] *= 1.01
  assert.match(qualifyNativeCameraEnclosure(f).failures.join('\n'), /uploaded projectionMatrix/)
})

test('normal components may span zero, but a zero original length or singular matrix is refused', () => {
  const f = fixture(), proof = qualifyNativeCameraEnclosure(f)
  assert.ok(proof.cameraProof.normal.minimumTransformedLength > 0)
  assert.ok(proof.cameraProof.normal.maxAngularBoundRadians > 0)
  const bad = { ...f, coreProof: { ...f.coreProof, cameraDomain: { ...f.coreProof.cameraDomain, objectNormalMinOriginalLength: 0 } } }
  assert.match(qualifyNativeCameraEnclosure(bad).failures.join('\n'), /object normal length/)
  f.closed.uniforms.get('normalMatrix')[0] = 0
  assert.match(qualifyNativeCameraEnclosure(f).failures.join('\n'), /uploaded normalMatrix/)
})

test('before-near triangle is excluded independently of a farther visible triangle sharing the same path', () => {
  const f = fixture({ positions: [-0.00001, -0.00001, 0.999, 0.00001, -0.00001, 0.999, 0, 0.00001, 0.999, -0.01, -0.01, 0, 0.01, -0.01, 0, 0, 0.01, 0] }), proof = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(proof.gaps, [])
  assert.deepEqual(proof.failures, [])
  assert.equal(proof.cameraProof.provedOutsideDomainCount, 1)
  assert.equal(proof.cameraProof.potentiallyVisibleTriangleCount, 1)
  assert.equal(proof.cameraProof.domains[0].status, 'proved-outside-homogeneous-clip-volume')
})

test('a potentially visible triangle straddling near or W is unmeasured, never divided through zero', () => {
  for (const depths of [[0.994, 0.996, 0.994], [0.9, 1.1, 0.9]]) {
    const f = fixture({ positions: [-0.00001, -0.00001, depths[0], 0.00001, -0.00001, depths[1], 0, 0.00001, depths[2]] }), proof = qualifyNativeCameraEnclosure(f)
    assert.ok(proof.gaps.some(reason => reason.includes('unresolved clip/warp/mask')))
    assert.equal(proof.cameraProof.domainStatus, 'unmeasured-required-projective-domain')
    assert.equal(proof.cameraProof.domains[0].status, 'ambiguous-required-w-near-far-clipped-domain')
  }
})

test('correlated homogeneous far plane admits a deep triangle entirely inside the actual clip volume', () => {
  const f = fixture({ positions: [-0.0001, -0.0001, 0.1, 0.0001, -0.0001, 0.9, 0, 0.0001, 0.5] })
  const proof = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(proof.gaps, [])
  assert.deepEqual(proof.failures, [])
  assert.ok(proof.cameraProof.domains[0].farClipLower > 0)
})

test('required footprints cannot silently cross a source scissor or later ordered opaque mask', () => {
  const f = fixture()
  f.expectedView.cameraSupports = [{ path: f.submitted.path, triangleIndex: 0, sourceFootprintPixels: [319, 239, 321, 241] }]
  f.expectedView.binding.sourceLayout.push({ viewId: 'later', rectSourcePixels: [320, 230, 10, 20], composite: null })
  const proof = qualifyNativeCameraEnclosure(f)
  assert.ok(proof.gaps.length > 0)
  assert.equal(proof.cameraProof.domains[0].status, 'ambiguous-required-ordered-mask-footprint')
  f.expectedView.binding.sourceLayout.pop()
  f.expectedView.rasterGeometry.destinationScissorBackingPixels = [0, 0, 320, 480]
  assert.equal(qualifyNativeCameraEnclosure(f).cameraProof.domains[0].status, 'ambiguous-required-source-scissor-footprint')
})

test('actual uploaded inverse warp and grid are independently checked; warp precedes mirror', () => {
  const f = fixture(); installWarp(f)
  const native = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(native.failures, [])
  assert.deepEqual(native.gaps, [])
  f.expectedView.binding.presentation = 'horizontal-mirror'
  const mirrored = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(mirrored.cameraProof.domains[0].source, native.cameraProof.domains[0].source)
  f.expectedView.rasterGeometry.warpSubmission.uniforms.get('inverseH')[0] = 2
  assert.match(qualifyNativeCameraEnclosure(f).failures.join('\n'), /uploaded inverseH/)
})

test('warp denominator near a required primitive cannot be hidden by a valid inverse matrix', () => {
  const f = fixture(); installWarp(f, [1, 0, 0, 0, 1, 0, -1 / 320, 0, 1])
  const proof = qualifyNativeCameraEnclosure(f)
  assert.ok(proof.gaps.length || proof.failures.length)
  assert.equal(proof.cameraProof.domainStatus, 'unmeasured-required-projective-domain')
  assert.equal(proof.cameraProof.domains[0].status, 'ambiguous-required-projective-warp-domain')
})

test('closed source profile rejects changed projection, indirect writes, defines and split-world correction order', () => {
  assert.equal(nativeCameraShaderProfile(shader, { normalsNeeded: true }).kind, 'closed-three-linear-camera-v1')
  assert.throws(() => nativeCameraShaderProfile(shader.replace('projectionMatrix * mvPosition', 'projectionMatrix * vec4(position, 1.0)')), /clip expression/)
  assert.throws(() => nativeCameraShaderProfile(shader.replace('gl_Position =', 'mutate(mvPosition); gl_Position =')), /indirect mutation/)
  assert.throws(() => nativeCameraShaderProfile(shader.replace('precision highp float;', '#define USE_INSTANCING\nprecision highp float;')), /USE_INSTANCING/)
  assert.throws(() => nativeCameraShaderProfile(shader.replace('precision highp float;', 'precision mediump float;')), /highp Float32/)
  assert.throws(() => nativeCameraShaderProfile(shader.replace('void main()', 'vec3 cameraDependent() { return cameraPosition; }\nvoid main()')), /Camera dependency hidden/)
  const spring = shader.replace('uniform mat4 modelViewMatrix;', 'uniform mat4 modelViewMatrix;\nuniform mat4 modelMatrix;\nuniform vec3 springWorldTranslationLow;')
    .replace('void main() {', 'void main() {\nvec3 springNewCentre;\nvec3 springNewTangent;\nspringCurve(springNewCentre, springNewTangent);')
    .replace('vec3 transformedNormal = objectNormal;', 'objectNormal = springNormal(objectNormal, springNewTangent);\nvec3 transformedNormal = objectNormal;')
    .replace('vec3 transformed = vec3(position);', 'vec3 transformed = springPosition(position, springNewCentre, springNewTangent);\nvec4 worldPosition = vec4(transformed, 1.0);\nworldPosition = vec4(modelMatrix[3].xyz + (mat3(modelMatrix) * worldPosition.xyz + springWorldTranslationLow), 1.0);')
  assert.equal(nativeCameraShaderProfile(spring, { spring: true, worldNeeded: true }).world, 'split-world-translation-low-inner-before-high')
  assert.throws(() => nativeCameraShaderProfile(spring.replace('modelMatrix[3].xyz + (mat3(modelMatrix) * worldPosition.xyz + springWorldTranslationLow)', 'modelMatrix[3].xyz + mat3(modelMatrix) * worldPosition.xyz + springWorldTranslationLow'), { spring: true, worldNeeded: true }), /world expression\/order/)
})

test('draw-range support excludes an unsubmitted before-near triangle, and nonfinite physical bytes are refused', () => {
  const f = fixture({ positions: [-0.00001, -0.00001, 0.999, 0.00001, -0.00001, 0.999, 0, 0.00001, 0.999, -0.01, -0.01, 0, 0.01, -0.01, 0, 0, 0.01, 0] })
  const domain = f.coreProof.cameraDomain, drawRange = { start: 3, count: 3, mode: 4 }
  f.submitted.drawRange = drawRange
  f.coreProof.cameraDomain = createNativeCameraDomainSummary({
    localActual: { actual: f.local, stride: 3, offset: 0, components: 3 },
    indices: Uint32Array.from({ length: f.count }, (_, i) => i), drawRange,
    localMaxComponentError: domain.localMaxComponentError, localBoundsF64: domain.localBoundsF64,
    objectNormalMinOriginalLength: 1, objectNormalMaxOriginalLength: 1,
    objectNormalMaxActualLength: 1, objectNormalMaxEuclideanErrorBound: 0, vertexCount: f.count,
  })
  const proof = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(proof.gaps, [])
  assert.deepEqual(proof.failures, [])
  assert.equal(proof.cameraProof.provedOutsideDomainCount, 0)
  assert.equal(proof.cameraProof.potentiallyVisibleTriangleCount, 1)
  const args = { localActual: { actual: Float32Array.of(NaN, 0, 0, 0, 0, 0, 0, 0, 0), stride: 3, offset: 0, components: 3 }, indices: Uint32Array.of(0, 1, 2), drawRange: { start: 0, count: 3, mode: 4 }, localMaxComponentError: [0, 0, 0], localBoundsF64: [0, 0, 0, 0, 0, 0], vertexCount: 3 }
  assert.throws(() => createNativeCameraDomainSummary(args), /Nonfinite all-vertex/)
  const warp = fixture(); installWarp(warp)
  warp.expectedView.rasterGeometry.warpSubmission.uniforms.get('mask')[0] = 1
  assert.throws(() => prepareNativeWarpSubmission(warp.expectedView.binding, warp.expectedView.rasterGeometry), /mask flag/)
})

test('Float32 input conversion and cancellation cannot disappear behind a small projected result', () => {
  const f = fixture({ positions: [100000, -0.01, 0, 100000.01, -0.01, 0, 100000, 0.01, 0], cameraPosition: [100000.003, 0, 1] })
  f.expectedView.cameraSupports = [{ path: f.submitted.path, triangleIndex: 0, sourceFootprintPixels: [319, 239, 320, 240] }]
  const proof = qualifyNativeCameraEnclosure(f)
  assert.ok(proof.fields.view.maxAbsoluteErrorBound > 0.003)
  assert.ok(proof.failures.some(reason => reason.includes('strict source policy')))
  const measured = validateNativeCameraSamples(proof, samples(f))
  assert.equal(measured.allComponentsInside, true, 'Measured arithmetic may fit while its finite source-pixel budget still fails')
})

test('horizontal mirror closes the actual quad law and rejects an unmirrored or additionally masked program', () => {
  const f = fixture({ positions: [0.05, -0.01, 0, 0.08, -0.01, 0, 0.065, 0.01, 0] })
  const native = qualifyNativeCameraEnclosure(f)
  f.expectedView.binding.presentation = 'horizontal-mirror'
  f.expectedView.rasterGeometry.mirrorSubmission = { vertexShader: presentationVertex, fragmentShader: mirrorFragment, uniforms: new Map([['image', Uint32Array.of(0)]]) }
  const mirrored = qualifyNativeCameraEnclosure(f)
  assert.deepEqual(mirrored.gaps, [])
  assert.deepEqual(mirrored.failures, [])
  assert.ok(native.cameraProof.domains[0].source[0][0] > 320)
  assert.ok(mirrored.cameraProof.domains[0].source[0][1] < 320)
  f.expectedView.rasterGeometry.mirrorSubmission.fragmentShader = mirrorFragment.replace('1.0-imageUv.x', 'imageUv.x')
  assert.throws(() => prepareNativeMirrorSubmission(f.expectedView.binding, f.expectedView.rasterGeometry), /coordinate\/support kernel/)
  f.expectedView.rasterGeometry.mirrorSubmission.fragmentShader = mirrorFragment.replace('void main() {', 'void main() { discard;')
  assert.throws(() => prepareNativeMirrorSubmission(f.expectedView.binding, f.expectedView.rasterGeometry), /coordinate\/support kernel/)
})

test('indexed reusable selected samples attribute a transient zero-W failure to its own vertex', () => {
  const f = fixture(), proof = qualifyNativeCameraEnclosure(f), values = samples(f)
  const reusable = { originalLocal: new Float64Array(3), originalObjectNormal: new Float64Array(3), view: new Float32Array(3), clip: new Float32Array(4), viewNormal: new Float32Array(3) }
  const result = validateNativeCameraSamples(proof, { vertexCount: f.count, read(index) {
    const source = values[index]
    reusable.originalLocal.set(source.originalLocal); reusable.originalObjectNormal.set(source.originalObjectNormal)
    reusable.view.set(source.view); reusable.clip.set(source.clip); reusable.viewNormal.set(source.viewNormal)
    if (index === 1) reusable.clip[3] = 0
    return reusable
  } })
  assert.equal(result.invalidPositiveWCount, 1)
  assert.equal(result.fields.clip.outsideCount, 1)
  assert.equal(result.fields.view.outsideCount, 0)
  assert.equal(result.fields.viewNormal.outsideCount, 0)
  assert.equal(result.allComponentsInside, false)
})

test('authentic point NDC/depth intervals consume the full same-camera reassociation bounds', () => {
  const f = fixture(), proof = qualifyNativeCameraEnclosure(f), bounds = proof.cameraProof.componentErrorBounds
  for (const sample of samples(f)) {
    const point = encloseNativeCameraPoint(sample.originalLocal, f.expectedView.cameraMatrices, { viewPositionBound: bounds.view, clipErrorBound: bounds.clip })
    assert.equal(point.status, 'inside'); assert.equal(point.projectable, true)
    for (let axis = 0; axis < 4; axis++) assert.ok(sample.clip[axis] >= point.clip[axis][0] && sample.clip[axis] <= point.clip[axis][1])
    for (let axis = 0; axis < 3; axis++) {
      const ndc = Math.fround(sample.clip[axis] / sample.clip[3])
      assert.ok(ndc >= point.ndc[axis][0] && ndc <= point.ndc[axis][1])
    }
    const depth = Math.fround(Math.fround(sample.clip[2] / sample.clip[3]) * 0.5 + 0.5)
    assert.ok(depth >= point.depth[0] && depth <= point.depth[1])
  }
  assert.throws(() => encloseNativeCameraPoint([0, 0, 0], f.expectedView.cameraMatrices, { viewPositionBound: proof.fields.view.maxAbsoluteErrorBound }), /Same fresh prior camera clip/)
})

test('point enclosures never divide near/zero-W ambiguity but preserve projectable XY-clipped vertices', () => {
  for (const z of [1, 0.999, 0.995]) {
    const f = fixture({ positions: [-0.01, -0.01, z, 0.01, -0.01, z, 0, 0.01, z] }), proof = qualifyNativeCameraEnclosure(f)
    const point = encloseNativeCameraPoint([0, 0, f.local[2]], f.expectedView.cameraMatrices, { viewPositionBound: proof.fields.view.maxAbsoluteErrorBound, clipErrorBound: proof.fields.clip.maxAbsoluteErrorBound })
    assert.notEqual(point.status, 'inside'); assert.equal(point.projectable, false)
    assert.equal(point.ndc, null); assert.equal(point.depth, null)
  }
  const outside = fixture({ positions: [2, -0.01, 0, 2.01, -0.01, 0, 2, 0.01, 0] }), outsideProof = qualifyNativeCameraEnclosure(outside)
  const point = encloseNativeCameraPoint([2, 0, 0], outside.expectedView.cameraMatrices, { viewPositionBound: outsideProof.fields.view.maxAbsoluteErrorBound, clipErrorBound: outsideProof.fields.clip.maxAbsoluteErrorBound })
  assert.equal(point.status, 'outside'); assert.equal(point.projectable, true)
  assert.ok(point.ndc[0][0] > 1); assert.ok(point.depth[0] >= 0 && point.depth[1] <= 1)
})

test('standalone projection encloses input conversion and cancellation in every dot reduction order', () => {
  const f = fixture(), projection = [...f.closed.projection], original = [1.00001, 1, -1]
  projection[0] = 100000; projection[4] = -100000
  const point = encloseNativeViewClipPoint(original, projection), uploaded = Float32Array.from(projection)
  assert.equal(point.projectable, true)
  for (const delta of [-1e-7, 0, 1e-7]) for (const order of [[0, 1, 2, 3], [3, 2, 1, 0], [1, 3, 0, 2]]) {
    const input = [Math.fround(original[0] + delta), Math.fround(original[1]), Math.fround(original[2]), 1]
    for (let row = 0; row < 4; row++) {
      let actual = 0
      for (const column of order) actual = Math.fround(actual + Math.fround(uploaded[row + 4 * column] * input[column]))
      assert.ok(actual >= point.clip[row][0] && actual <= point.clip[row][1], `row ${row}, delta ${delta}, order ${order}`)
    }
  }
  for (const viewPoint of [[0, 0, 0], [0, 0, -0.001], [0, 0, -0.005]]) {
    const denied = encloseNativeViewClipPoint(viewPoint, f.closed.projection)
    assert.equal(denied.projectable, false); assert.equal(denied.ndc, null); assert.equal(denied.depth, null)
  }
})
