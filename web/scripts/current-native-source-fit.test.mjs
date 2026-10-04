import test from 'node:test'
import assert from 'node:assert/strict'
import { access, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { CURRENT_NATIVE_RAW_SHA256, CURRENT_NATIVE_DELIVERY_SHA256, jsonDigest, sha256 } from './native-model-byte-proof.mjs'

const sourceFitURL = process.env.CURRENT_NATIVE_SOURCE_FIT_MODULE
  ? pathToFileURL(resolve(process.env.CURRENT_NATIVE_SOURCE_FIT_MODULE)) : new URL('./current-native-source-fit.mjs', import.meta.url)
const { currentNativeFitSourceTuple, prepareCurrentNativeFitSource, currentNativeFitWorldPoint,
  independentCurrentNativeFitRows, assertPrivateCurrentNativeFitOutput, createExactAssociatedCurrentNativeFitDefinitions,
  exportCurrentNativeSourceFit } = await import(sourceFitURL.href)
const axisFitURL = process.env.CURRENT_NATIVE_AXIS_FIT_MODULE
  ? pathToFileURL(resolve(process.env.CURRENT_NATIVE_AXIS_FIT_MODULE)) : new URL('./current-native-axis-fit.mjs', import.meta.url)
const { createCurrentNativeAxisFitDefinitions } = await import(axisFitURL.href)
const privateRoot = resolve(dirname(fileURLToPath(sourceFitURL)), '../.vite/verification-output')

// Deliberately three vertices, not a fabricated CURRENT462 inventory. These
// arithmetic fixtures prove refusal/coordinate behavior only; the root's actual
// pinned original-CPU -> raw -> world CLI smoke provides native-world evidence.
const hash = 'a'.repeat(64), imageHash = 'b'.repeat(64)
function sourceFixture() {
  const sourceImage = { frameIndex: 809, sourceSha256: hash, sha256Bgr8: imageHash, pixelFormat: 'bgr8', width: 1920, height: 1080 }
  const landmark = { anchorId: 'genuine-source-feature', role: 'fit', pixel: [783, 110], status: 'observed', uncertaintyPx: 4, method: 'manual' }
  const frame = { sourceImage, timeSeconds: 27, decodedTimeSeconds: 26.993633, shotId: 'actual-shot', landmarks: [landmark], mechanicalState: { input: null } }
  const input = { crankTurns: 0.25, amplitudes: Array(20).fill(0), phases: Array(20).fill(0), gearing: 'medium-medium', magnification: 1,
    setup: { counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0, coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 } }
  const authoredFrame = structuredClone(frame)
  authoredFrame.input = input
  authoredFrame.provenance = { kind: 'chosen-feasible', unobservedInputFields: ['crankTurns'] }
  const decodedFrame = { frameIndex: 809, sourceSha256: hash, sha256Bgr8: imageHash, decodedTimestampTicks: 809809, timeBase: '1/30000', decodedTimeSeconds: 809809 / 30000 }
  return { originalObservations: { source: { videoId: 'source-only-test', sha256: hash, width: 1920, height: 1080 }, frames: [frame] },
    authoredFrame, viewId: 'main', decodedFrame,
    inputSelection: { field: 'input', state: 'chosen-unmeasured', evidence: 'Explicit independently selected candidate; not source recovered', ambiguities: ['unobserved crank home'] } }
}

function triangleFixture() {
  const primitive = { path: 'test/exact-triangle', rawPrimitiveSHA256: hash, nodeIndex: 4, meshIndex: 7, primitiveIndex: 0, instanceOf: null,
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]), index: new Uint32Array([0, 1, 2]) }
  const original = { path: primitive.path, association: { nodeIndex: 4, meshIndex: 17, primitiveIndex: 0 }, instanceOf: null, spring: null,
    attributes: { position: { array: Float32Array.from(primitive.positions), itemSize: 3, count: 3 } }, canonicalIndices: Uint32Array.from(primitive.index) }
  // Proper 90-degree Z rotation and a translation; binary64 translation has a
  // component lost by f32, so downcasting the independently solved pose fails.
  const pose = { path: primitive.path, effectiveVisibility: true, matrixWorld: new Float64Array([0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 1 + 2 ** -40, 2, 3, 1]) }
  const witness = { anchorId: 'surface-point', partPath: primitive.path, rawPrimitiveSHA256: hash, sourceFeatureEvidenceSHA256: imageHash,
    kind: 'triangle-point', triangleIndex: 0, barycentric: [0.5, 0.25, 0.25] }
  return { primitive, original, pose, witness }
}

test('independent exact PTS is retained separately from original rounded decoded time', () => {
  const f = sourceFixture(), s = prepareCurrentNativeFitSource(f)
  assert.equal(s.sourceBinding.decodedTimestampTicks, 809809)
  assert.equal(s.sourceBinding.decodedTimeSeconds, 809809 / 30000)
  assert.equal(s.sourceBinding.recordedOriginalDecodedTimeSeconds, 26.993633)
  assert.deepEqual(s.partOverrides, [])
  assert.equal(f.originalObservations.frames[0].decodedTimeSeconds, 26.993633)
})

test('canonical gray8 source identity remains gray8; converted or dual image identities refuse', () => {
  const f = sourceFixture()
  for (const image of [f.originalObservations.frames[0].sourceImage, f.authoredFrame.sourceImage]) {
    image.pixelFormat = 'gray8'; image.sha256Gray8 = image.sha256Bgr8; delete image.sha256Bgr8
  }
  f.decodedFrame.sha256Gray8 = f.decodedFrame.sha256Bgr8; delete f.decodedFrame.sha256Bgr8
  const prepared = prepareCurrentNativeFitSource(f)
  assert.equal(prepared.sourceBinding.sourceImage.pixelFormat, 'gray8')
  assert.equal(prepared.sourceBinding.sourceImage.sha256Gray8, imageHash)
  assert.equal(prepared.sourceBinding.sourceImage.sha256Bgr8, undefined)
  const converted = structuredClone(f)
  converted.decodedFrame.sha256Bgr8 = converted.decodedFrame.sha256Gray8; delete converted.decodedFrame.sha256Gray8
  assert.throws(() => prepareCurrentNativeFitSource(converted), Error)
  const dual = structuredClone(f)
  dual.originalObservations.frames[0].sourceImage.sha256Bgr8 = imageHash
  assert.throws(() => prepareCurrentNativeFitSource(dual), Error)
})

test('unprobed PTS, wrong original image and source clock beyond unchanged half second refuse', () => {
  for (const mutate of [f => { f.decodedFrame.decodedTimestampTicks++ }, f => { f.decodedFrame.sha256Bgr8 = 'c'.repeat(64) },
    f => { f.originalObservations.frames[0].timeSeconds = 26; f.authoredFrame.timeSeconds = 26 }]) {
    const f = sourceFixture(); mutate(f)
    assert.throws(() => currentNativeFitSourceTuple(f.originalObservations, f.originalObservations.frames[0], 'main', f.decodedFrame), /PTS|frame\/PTS|clock/)
  }
})

test('authored roles, actual pixels and source uncertainty cannot be changed or omitted', () => {
  for (const mutate of [l => { l.role = 'check' }, l => { l.pixel[0] += 1 }, l => { l.uncertaintyPx = 40 }]) {
    const f = sourceFixture(); mutate(f.authoredFrame.landmarks[0])
    assert.throws(() => prepareCurrentNativeFitSource(f), /role\/pixel\/uncertainty/)
  }
})

test('chosen authored input cannot be called independently measured, and partial inputs never default', () => {
  const f = sourceFixture(); f.inputSelection.state = 'independently-measured'
  assert.throws(() => prepareCurrentNativeFitSource(f), /cannot be promoted/)
  const partial = sourceFixture(); delete partial.authoredFrame.input.setup.counterHeightM
  assert.throws(() => prepareCurrentNativeFitSource(partial), /complete explicit 51-field/)
  const chosen = sourceFixture(); chosen.authoredFrame.chosenInput = chosen.authoredFrame.input
  chosen.inputSelection.field = 'chosenInput'; chosen.inputSelection.state = 'independently-measured'
  assert.throws(() => prepareCurrentNativeFitSource(chosen), /cannot be promoted/)
})

test('exact raw triangle barycentric point uses original binary64 rigid world pose', () => {
  const f = triangleFixture(), p = currentNativeFitWorldPoint(f)
  assert.deepEqual(p.localMetres, [0.25, 0.25, 0])
  assert.deepEqual(p.worldMetres, [0.75 + 2 ** -40, 2.25, 3])
  assert.notEqual(p.worldMetres[0], Math.fround(p.worldMetres[0]))
  assert.deepEqual(p.supportTriangleIndices, [0])
})

test('missing/hidden pose, raw ordinal mismatch and unsupported pseudo-feature remain refused', () => {
  const hidden = triangleFixture(); hidden.pose.effectiveVisibility = false
  assert.throws(() => currentNativeFitWorldPoint(hidden), /missing or hidden/)
  const missing = triangleFixture(); delete missing.pose
  assert.throws(() => currentNativeFitWorldPoint(missing), /missing or hidden/)
  const foreign = triangleFixture(); foreign.original.association.nodeIndex++
  assert.throws(() => currentNativeFitWorldPoint(foreign), /ancestry differs/)
  const pseudo = triangleFixture(); pseudo.witness.kind = 'nearest-vertex'
  assert.throws(() => currentNativeFitWorldPoint(pseudo), /unsupported.*kind/)
  const spring = triangleFixture(); spring.original.spring = { stock: 'channel', restLengthM: 0.2 }
  assert.throws(() => currentNativeFitWorldPoint(spring), /pinned original spring oracle/)
})

test('deduplicated delivery mesh ordinals differ legitimately, but changed decoded topology refuses', () => {
  const f = triangleFixture()
  assert.notEqual(f.original.association.meshIndex, f.primitive.meshIndex)
  assert.deepEqual(currentNativeFitWorldPoint(f).worldMetres, [0.75 + 2 ** -40, 2.25, 3])
  const position = triangleFixture(); position.original.attributes.position.array[3] = 0.5
  assert.throws(() => currentNativeFitWorldPoint(position), /delivery POSITION differs/)
  const index = triangleFixture(); index.original.canonicalIndices[0] = 2
  assert.throws(() => currentNativeFitWorldPoint(index), /delivery indices differ/)
})

test('32 coincident apex indices are one physical FIT, and cannot provide held-out CHECKs', () => {
  const rows = Array.from({ length: 32 }, (_, i) => ({ status: 'world-exported', worldMetres: [0.125, 0.25, 0.5],
    originalLandmark: { anchorId: `apex-seam-${i}`, role: i < 30 ? 'fit' : 'check', pixel: [100, 200], uncertaintyPx: 4 } }))
  const originals = structuredClone(rows.map(r => r.originalLandmark))
  independentCurrentNativeFitRows(rows)
  assert.equal(rows.filter(r => r.status === 'world-exported').length, 1)
  assert.equal(rows.filter(r => r.status === 'world-exported' && r.originalLandmark.role === 'check').length, 0)
  assert.deepEqual(rows.map(r => r.originalLandmark), originals)
  assert.equal(rows[31].duplicateOf, 'apex-seam-0')
  assert.match(rows[31].reason, /one support/)
})

test('private command never targets canonical tracks or parent-directory escape', () => {
  assert.throws(() => assertPrivateCurrentNativeFitOutput('web/content/v39/NAsM30MAHLg.source-track.json'), /never canonical/)
  assert.throws(() => assertPrivateCurrentNativeFitOutput('web/.vite/verification-output/../../content/false-track.json'), /never canonical/)
})

function associationFixture() {
  const f = triangleFixture(), s = sourceFixture(), source = prepareCurrentNativeFitSource(s)
  const originalAnchor = { id: source.landmarks[0].anchorId, partPath: f.primitive.path, partLocalMetres: [0.25, 0.25, 0], correspondenceEvidence: 'Actual independently measured source feature' }
  s.originalObservations.anchors = [originalAnchor]
  f.primitive.rawPath = f.primitive.path
  const positions = { array: f.primitive.positions, itemSize: 3, count: 3, componentType: 5126, normalized: false, bytes: new Uint8Array(f.primitive.positions.buffer) }
  const indices = { array: f.primitive.index, itemSize: 1, count: 3, componentType: 5125, normalized: false, bytes: new Uint8Array(f.primitive.index.buffer) }
  f.primitive.attributes = { POSITION: positions }
  f.primitive.material = null
  f.original.restMatrixF64 = f.pose.matrixWorld
  const descriptor = { mode: 4, attributes: { POSITION: { componentType: 5126, type: 'VEC3', count: 3, normalized: false, typedBytesSha256: sha256(positions.bytes) } },
    indices: { componentType: 5125, type: 'SCALAR', count: 3, normalized: false, typedBytesSha256: sha256(indices.bytes) }, material: null }
  const anchor = { ...structuredClone(originalAnchor), nativeAssociation: { status: 'mapped', proof: {
    method: 'exact-original-native-local-feature-v1', currentSource: { sha256: CURRENT_NATIVE_RAW_SHA256 }, qualifiedPartPath: f.primitive.path,
    historicalAnchorSha256: jsonDigest(originalAnchor), currentNodeIndex: f.primitive.nodeIndex, currentWorldMatrix: Array.from(f.pose.matrixWorld),
    // This intentionally nonsensical historical world point must not enter the
    // genuine raw local construction; actual CPU posing occurs in another API.
    historicalWorldMetres: [999, 999, 999], primitives: [descriptor],
  } } }
  const meshes = []; meshes[f.primitive.meshIndex] = { primitives: [{ indices: 0 }] }
  const args = { nativeModel: { primitives: new Map([[f.primitive.path, f.primitive]]), document: { meshes }, accessor: () => indices },
    poseOracle: { inventory: { drawables: [f.original] } }, originalObservations: s.originalObservations, currentAnchors: [anchor],
    source, selections: [{ anchorId: originalAnchor.id }] }
  return { args, anchor, originalAnchor, descriptor }
}

test('an unchanged typed association still needs an actual closed raw feature, not its historical world point', () => {
  const { args, anchor, originalAnchor, descriptor } = associationFixture()
  const actual = createExactAssociatedCurrentNativeFitDefinitions(args)[0]
  assert.equal(actual.witness.kind, 'triangle-point')
  assert.deepEqual(actual.witness.barycentric, [0.5, 0.25, 0.25])
  anchor.partLocalMetres = [0.25, 0.25, 1e-9]
  assert.match(createExactAssociatedCurrentNativeFitDefinitions(args)[0].unavailableReason, /local point changed/)
  originalAnchor.partLocalMetres = [...anchor.partLocalMetres]
  anchor.nativeAssociation.proof.historicalAnchorSha256 = jsonDigest(originalAnchor)
  assert.match(createExactAssociatedCurrentNativeFitDefinitions(args)[0].unavailableReason, /no closed raw surface witness/)
  anchor.partLocalMetres = [0.25, 0.25, 0]
  originalAnchor.partLocalMetres = [...anchor.partLocalMetres]
  anchor.nativeAssociation.proof.historicalAnchorSha256 = jsonDigest(originalAnchor)
  descriptor.attributes.POSITION.typedBytesSha256 = 'e'.repeat(64)
  assert.match(createExactAssociatedCurrentNativeFitDefinitions(args)[0].unavailableReason, /no closed raw surface witness/)
})

function exportFixture() {
  const s = sourceFixture(), f = triangleFixture()
  const barycentrics = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.5, 0.5, 0], [0.5, 0, 0.5],
    [0, 0.5, 0.5], [0.5, 0.25, 0.25], [0.25, 0.5, 0.25]]
  const landmarks = barycentrics.map((_, i) => ({ anchorId: `test-only-export-point-${i}`, role: i < 6 ? 'fit' : 'check',
    pixel: [400 + i * 30, 300 + i * 20], status: 'observed', uncertaintyPx: 4, method: 'test-only-arithmetic' }))
  s.originalObservations.frames[0].landmarks = landmarks
  s.authoredFrame.landmarks = structuredClone(landmarks)
  s.originalObservations.model = { fixture: 'one-triangle-arithmetic-only' }
  s.originalObservations.anchors = landmarks.map(l => ({ id: l.anchorId, description: 'Independent test-only point identity' }))
  const source = prepareCurrentNativeFitSource(s)
  const featureDefinitions = landmarks.map((originalLandmark, i) => {
    const correspondence = { state: 'chosen-unmeasured', evidence: { fixture: 'test-only-triangle-point' } }
    const evidence = { sourceBinding: source.sourceBinding, originalLandmark, correspondence }
    return { ...evidence, witness: { ...f.witness, anchorId: originalLandmark.anchorId,
      barycentric: barycentrics[i], sourceFeatureEvidenceSHA256: jsonDigest(evidence) } }
  })
  return { ...s, featureDefinitions, nativeModel: { rawSHA256: CURRENT_NATIVE_RAW_SHA256, primitives: new Map([[f.primitive.path, f.primitive]]) },
    poseOracle: { inventory: { rawSHA256: CURRENT_NATIVE_RAW_SHA256, deliverySHA256: CURRENT_NATIVE_DELIVERY_SHA256,
      closureSHA256: hash, drawables: [f.original] }, solve: () => ({ drawables: [f.pose] }) },
    provenance: Object.fromEntries(['originalObservationsSHA256', 'authoredFrameSHA256', 'selectionSHA256', 'decodedFrameSHA256'].map(k => [k, hash])) }
}

function axisFixture() {
  const s = sourceFixture(), source = prepareCurrentNativeFitSource(s), vertices = [], indices = []
  for (const z of [-1, 1]) for (let k = 0; k < 8; k++) vertices.push(Math.cos(k * Math.PI / 4), Math.sin(k * Math.PI / 4), z)
  for (let k = 0; k < 8; k++) {
    const a = k, b = (k + 1) % 8
    indices.push(a, b, b + 8, a, b + 8, a + 8)
  }
  for (const base of [0, 8]) for (let k = 1; k < 7; k++) indices.push(base, base + k, base + k + 1)
  const primitive = { path: 'test-only/axis-cylinder', rawPath: 'test-only/axis-cylinder', rawPrimitiveSHA256: hash,
    nodeIndex: 4, primitiveIndex: 0, instanceOf: null, positions: new Float32Array(vertices), index: new Uint32Array(indices) }
  const id = source.landmarks[0].anchorId
  s.originalObservations.anchors = [{ id, description: 'Test-only physical shaft axis' }]
  const control = { anchorId: id, rawNodeIndex: 4, rawPrimitiveIndex: 0, rawPartPath: primitive.rawPath, rawPrimitiveSHA256: hash,
    axisIndex: 2, sectionCoordinates: [-0.5, 0.5], axisPointCoordinate: 'maximum',
    sourceSemanticEvidence: 'Independent test-only axis declaration; no source/native qualification', sourceRasterImageSHA256: imageHash }
  return { nativeModel: { rawSHA256: CURRENT_NATIVE_RAW_SHA256, primitives: new Map([[primitive.path, primitive]]) },
    originalObservations: s.originalObservations, source, controls: [control] }
}

for (const field of ['timeSeconds', 'decodedTimeSeconds']) {
  for (const [label, value] of [['numeric string', '0'], ['null', null], ['NaN', NaN]]) {
    test(`original ${field} refuses ${label} instead of arithmetic coercion`, () => {
      const s = sourceFixture(), frame = s.originalObservations.frames[0]
      frame.timeSeconds = 0; frame.decodedTimeSeconds = 0
      s.decodedFrame.decodedTimestampTicks = 0; s.decodedFrame.decodedTimeSeconds = 0
      const positive = currentNativeFitSourceTuple(s.originalObservations, frame, 'main', s.decodedFrame)
      assert.equal(positive.timeSeconds, 0)
      assert.equal(positive.recordedOriginalDecodedTimeSeconds, 0)
      frame[field] = value
      assert.throws(() => currentNativeFitSourceTuple(s.originalObservations, frame, 'main', s.decodedFrame), /finite numeric original source clocks/)
    })
  }
}

test('matching original and authored string clocks cannot prepare a consumable packet', () => {
  const s = sourceFixture()
  assert.equal(prepareCurrentNativeFitSource(s).sourceBinding.timeSeconds, 27)
  for (const frame of [s.originalObservations.frames[0], s.authoredFrame]) {
    frame.timeSeconds = '27'; frame.decodedTimeSeconds = '26.993633'
  }
  assert.throws(() => prepareCurrentNativeFitSource(s), /finite numeric original source clocks/)
})

for (const field of ['imagePlaneWarp', 'resolvedImagePlaneWarp']) {
  for (const location of ['original frame', 'original view', 'authored frame', 'authored view']) {
    for (const warp of [{ kind: 'independent-test-only-corner-interior-obligation' }, false, 0, '']) {
      test(`${location} ${field}=${JSON.stringify(warp)} keeps the camera-only export ineligible`, () => {
        const args = exportFixture()
        if (location.endsWith('view')) {
          args.originalObservations.frames[0].views = [{ id: 'main', rectSourcePixels: [0, 0, 1920, 1080] }]
          args.authoredFrame.views = [{ id: 'main', rectSourcePixels: [0, 0, 1920, 1080], input: args.authoredFrame.input,
            provenance: args.authoredFrame.provenance }]
        }
        const positive = exportCurrentNativeSourceFit(args)
        assert.equal(positive.eligibility.ready, true)
        assert.deepEqual([positive.eligibility.distinctFitCount, positive.eligibility.distinctCheckCount], [6, 2])
        const frame = location.startsWith('original') ? args.originalObservations.frames[0] : args.authoredFrame
        const owner = location.endsWith('view') ? frame.views[0] : frame
        owner[field] = null
        assert.equal(exportCurrentNativeSourceFit(args).eligibility.ready, true)
        owner[field] = warp
        assert.deepEqual(prepareCurrentNativeFitSource(args).imagePlaneWarp, warp)
        const refused = exportCurrentNativeSourceFit(args)
        assert.equal(refused.eligibility.ready, false)
        assert.ok(refused.eligibility.reasons.some(r => /camera-only fit refuses warped views/.test(r)))
        assert.equal(refused.sourceAcceptance, false)
        assert.equal(refused.nativeAcceptance, false)
        assert.deepEqual(refused.original.frame, args.originalObservations.frames[0])
        assert.deepEqual(refused.authored.frame, args.authoredFrame)
      })
    }
  }
}

test('a warp owned only by a different view cannot block the selected unwarped view', () => {
  const args = exportFixture()
  args.originalObservations.frames[0].views = [
    { id: 'main', rectSourcePixels: [0, 0, 1920, 1080] },
    { id: 'unselected', rectSourcePixels: [0, 0, 1920, 1080], resolvedImagePlaneWarp: false },
  ]
  args.authoredFrame.views = [
    { id: 'main', rectSourcePixels: [0, 0, 1920, 1080], input: args.authoredFrame.input, provenance: args.authoredFrame.provenance },
    { id: 'unselected', rectSourcePixels: [0, 0, 1920, 1080], imagePlaneWarp: false },
  ]
  assert.equal(prepareCurrentNativeFitSource(args).imagePlaneWarp, null)
  assert.equal(exportCurrentNativeSourceFit(args).eligibility.ready, true)
})

for (const location of ['original', 'current']) for (const reverse of [false, true]) {
  test(`exact association refuses duplicate ${location} anchor identities${reverse ? ' in reverse order' : ''}`, () => {
    const { args, anchor, originalAnchor } = associationFixture()
    assert.equal(createExactAssociatedCurrentNativeFitDefinitions(args)[0].witness.kind, 'triangle-point')
    const conflicting = structuredClone(location === 'original' ? originalAnchor : anchor)
    if (location === 'original') conflicting.description = 'Conflicting source identity'
    else conflicting.nativeAssociation.status = 'unavailable'
    const rows = [location === 'original' ? originalAnchor : anchor, conflicting]
    if (reverse) rows.reverse()
    if (location === 'original') args.originalObservations.anchors = rows
    else args.currentAnchors = rows
    assert.throws(() => createExactAssociatedCurrentNativeFitDefinitions(args), /duplicate anchor identity/)
  })
}

for (const reverse of [false, true]) {
  test(`axis preparation refuses duplicate source anchor identities${reverse ? ' in reverse order' : ''}`, () => {
    const args = axisFixture()
    const positive = createCurrentNativeAxisFitDefinitions(args)[0]
    assert.equal(positive.witness.kind, 'geometric-axis')
    assert.equal(positive.rawAxisGeometry.pointIsSurfacePoint, false)
    const original = args.originalObservations.anchors[0], conflicting = { ...original, description: 'Conflicting axis source identity' }
    args.originalObservations.anchors = reverse ? [conflicting, original] : [original, conflicting]
    assert.throws(() => createCurrentNativeAxisFitDefinitions(args), /duplicate anchor identity/)
  })

  test(`world export refuses duplicate source anchor identities${reverse ? ' in reverse order' : ''}`, () => {
    const args = exportFixture()
    assert.equal(exportCurrentNativeSourceFit(args).eligibility.ready, true)
    const original = args.originalObservations.anchors[0], conflicting = { ...original, description: 'Conflicting original source identity' }
    args.originalObservations.anchors.push(conflicting)
    if (reverse) args.originalObservations.anchors.reverse()
    assert.throws(() => exportCurrentNativeSourceFit(args), /duplicate anchor identity/)
  })
}

test('private output admits a new nested private file but refuses symlink-parent escape before writing', async () => {
  await mkdir(privateRoot, { recursive: true })
  const owned = await mkdtemp(join(privateRoot, 'source-fit-output-test-'))
  const external = await mkdtemp(join(tmpdir(), 'source-fit-external-test-'))
  try {
    const nested = join(owned, 'nested')
    await mkdir(nested)
    const positive = join(nested, 'private-packet.json')
    await writeFile(assertPrivateCurrentNativeFitOutput(positive), 'inert private packet\n', { flag: 'wx' })
    assert.equal(await readFile(positive, 'utf8'), 'inert private packet\n')
    await assert.rejects(writeFile(assertPrivateCurrentNativeFitOutput(positive), 'replacement', { flag: 'wx' }), { code: 'EEXIST' })

    const sentinel = join(external, 'sentinel.txt')
    await writeFile(sentinel, 'owned external sentinel\n', { flag: 'wx' })
    await symlink(external, join(owned, 'linked'), 'dir')
    const escaped = join(external, 'must-remain-absent.json')
    let refusal
    try {
      await writeFile(assertPrivateCurrentNativeFitOutput(join(owned, 'linked', 'must-remain-absent.json')), 'inert escaped packet\n', { flag: 'wx' })
    } catch (error) { refusal = error }
    let escapedExists = true
    try { await access(escaped) } catch (error) { if (error.code === 'ENOENT') escapedExists = false; else throw error }
    assert.equal(escapedExists, false, 'an admitted parent symlink must not create even an inert external packet')
    assert.match(refusal?.message ?? '', /never canonical/)
    assert.equal(await readFile(sentinel, 'utf8'), 'owned external sentinel\n')

    const finalLink = join(nested, 'final-link.json')
    await symlink(sentinel, finalLink)
    await assert.rejects(writeFile(assertPrivateCurrentNativeFitOutput(finalLink), 'replacement', { flag: 'wx' }), { code: 'EEXIST' })
    assert.equal(await readFile(sentinel, 'utf8'), 'owned external sentinel\n')
  } finally {
    await rm(owned, { recursive: true, force: true })
    await rm(external, { recursive: true, force: true })
  }
})

async function privateRootGuardFixture(web) {
  const scripts = join(web, 'scripts'), original = fileURLToPath(sourceFitURL), moduleName = basename(original)
  await mkdir(scripts, { recursive: true })
  // Materialize the immutable module under test without rewriting its source.
  // Symlink sibling modules so their own original import contexts remain intact.
  await writeFile(join(scripts, moduleName), await readFile(original), { flag: 'wx' })
  for (const name of await readdir(dirname(original))) {
    if (name.endsWith('.mjs') && name !== moduleName) await symlink(join(dirname(original), name), join(scripts, name))
  }
  const alias = `${web}-alias`
  await symlink(web, alias, 'dir')
  const module = await import(pathToFileURL(join(alias, 'scripts', moduleName)).href)
  return module.assertPrivateCurrentNativeFitOutput
}

for (const redirectedEntry of ['verification-output', '.vite']) {
  test(`a redirected ${redirectedEntry} cannot become private output authority`, async () => {
    const owned = await mkdtemp(join(tmpdir(), 'source-fit-root-redirect-test-'))
    try {
      const web = join(owned, 'web'), fixturePrivateRoot = join(web, '.vite', 'verification-output')
      const guard = await privateRootGuardFixture(web)
      const nested = join(fixturePrivateRoot, 'nested')
      await mkdir(nested, { recursive: true })
      const positive = join(nested, 'private-packet.json')
      await writeFile(guard(positive), 'inert private packet\n', { flag: 'wx' })
      assert.equal(await readFile(positive, 'utf8'), 'inert private packet\n')
      await assert.rejects(writeFile(guard(positive), 'replacement', { flag: 'wx' }), { code: 'EEXIST' })
      await symlink(nested, join(fixturePrivateRoot, 'within-private'), 'dir')
      const withinPrivate = join(fixturePrivateRoot, 'within-private', 'another-private-packet.json')
      await writeFile(guard(withinPrivate), 'inert internal-alias packet\n', { flag: 'wx' })
      assert.equal(await readFile(join(nested, 'another-private-packet.json'), 'utf8'), 'inert internal-alias packet\n')

      const external = join(owned, 'external-inert-tree')
      const externalOutputRoot = redirectedEntry === '.vite' ? join(external, 'verification-output') : external
      await mkdir(externalOutputRoot, { recursive: true })
      const sentinel = join(externalOutputRoot, 'sentinel.txt')
      await writeFile(sentinel, 'owned external sentinel\n', { flag: 'wx' })
      const entry = redirectedEntry === '.vite' ? join(web, '.vite') : fixturePrivateRoot
      await rm(entry, { recursive: true })
      await symlink(external, entry, 'dir')
      const output = join(fixturePrivateRoot, 'must-remain-absent.json')
      let refusal
      try { await writeFile(guard(output), 'inert escaped packet\n', { flag: 'wx' }) }
      catch (error) { refusal = error }
      let escapedExists = true
      try { await access(join(externalOutputRoot, 'must-remain-absent.json')) }
      catch (error) { if (error.code === 'ENOENT') escapedExists = false; else throw error }
      assert.equal(escapedExists, false, 'a redirected private root must not authorize even an inert external packet')
      assert.match(refusal?.message ?? '', /never canonical/)
      assert.equal(await readFile(sentinel, 'utf8'), 'owned external sentinel\n')
    } finally {
      await rm(owned, { recursive: true, force: true })
    }
  })
}
