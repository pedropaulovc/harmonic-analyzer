import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createNativeRunBinding, createNativeRunRasterGeometry } from './native-qualification-run.mjs'
import { sourceLayoutForViews } from './verify-reference.mjs'

const sourceSHA = '1'.repeat(64), imageSHA = '2'.repeat(64), codeSHA = '3'.repeat(64)
const retainedTrack = JSON.parse(await readFile(new URL('../content/v39/NAsM30MAHLg.source-track.json', import.meta.url), 'utf8'))
const retainedFractionalView = retainedTrack.frames.find(frame => frame.sourceImage.frameIndex === 1501).views.find(view => view.id === 'right-operation-top')
// Borrow only retained camera/ROI numbers for arithmetic tests. The synthetic
// clock/context below never admits a source camera, source body or native run.
function fixture() {
  const image = { frameIndex: 1, pixelFormat: 'bgr8', width: 1920, height: 1080, sourceSha256: sourceSHA, sha256Bgr8: imageSHA }
  const camera = { positionMetres: [0, 0, 2], quaternion: [0, 0, 0, 1], verticalFovDegrees: 40, principalPointViewportPixels: [960, 540] }
  const input = { crankTurns: 0, gearing: 'direct', magnification: 1, amplitudes: Array(20).fill(0), phases: Array(20).fill(0), setup: {} }
  const view = { id: 'main', rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', camera, input }
  const frame = { timeSeconds: 1, decodedTimeSeconds: 1, shotId: 'source-shot', sourceImage: image, views: [view], landmarks: [] }
  const layout = sourceLayoutForViews(frame.views)
  const shared = { viewId: view.id, timeSeconds: 1, sourceLayout: layout, resolvedImagePlaneWarp: null }
  const capture = { ...shared, status: 'captured', drawRevision: 7 }
  const mechanism = { ...shared, status: 'rendered', method: 'actual-native-mechanism-solve', sourceDrawRevision: 7, input }
  const state = { ...shared, status: 'captured', drawRevision: 7, completedDrawEpoch: 11, camera, rectSourcePixels: view.rectSourcePixels,
    presentation: 'native', nativeViewportBackingPixels: [800, 450] }
  const response = { actual: { videoId: 'original', playerVideoId: 'original', mode: 'reference-review', playerState: 'paused',
    modelTime: 1, sourceDrawTimeSeconds: 1, sourceDrawRevision: 7, views: [{ ...view, sourceLayout: layout, resolvedImagePlaneWarp: null }] },
    captures: [{ viewId: view.id, capture, mechanism }], native: { paused: true, seeking: false, mediaTime: 1 } }
  const record = { id: 'original', track: { source: { videoId: 'original', sha256: sourceSHA } },
    native: { observedSha256: sourceSHA, pts: [0, 1], ptsTicks: ['0', '30000'], timeBase: '1/30000' } }
  return { record, frame, view, response, state, codeClosureSHA256: codeSHA }
}

test('exact native tick authority comes from the independent probe when the authored frame omits it', () => {
  const args = fixture(), binding = createNativeRunBinding(args)
  assert.equal(binding.decodedTimestampTicks, '30000')
  assert.equal(binding.timeBase, '1/30000')
  delete args.record.native.ptsTicks
  assert.throws(() => createNativeRunBinding(args), /Independently probed native ticks/)
})

test('nearby authored timestamp ticks are not an exposure alias', () => {
  const args = fixture()
  args.frame.decodedTimestampTicks = '30001'; args.frame.timeBase = '1/30000'
  assert.throws(() => createNativeRunBinding(args), /different original exposure/)
})

test('gray-only images cannot satisfy native source BGR8 identity', () => {
  const args = fixture()
  args.frame.sourceImage = { ...args.frame.sourceImage, pixelFormat: 'gray8', sha256Gray8: imageSHA }
  delete args.frame.sourceImage.sha256Bgr8
  assert.throws(() => createNativeRunBinding(args), /strict original BGR8/)
})

test('a stale same-time GPU epoch or complete physical input change cannot bind to reviewed source', () => {
  const stale = fixture(); stale.state.drawRevision = 6
  assert.throws(() => createNativeRunBinding(stale), /current source draw/)
  const changed = fixture()
  changed.response.captures[0].mechanism.input = { ...changed.view.input, crankTurns: 0.25 }
  assert.throws(() => createNativeRunBinding(changed), /full physical input differs/)
})

test('ordered view provenance is part of the closed physical/source binding', () => {
  const args = fixture()
  args.state.sourceLayout = [{ ...args.state.sourceLayout[0], compositeProvenance: { kind: 'chosen-unmeasured', evidence: 'changed source weight choice' } }]
  assert.throws(() => createNativeRunBinding(args), /ordered layout\/resolved warp differs/)
})

test('fractional letterboxing retains the source gate instead of rounding it to a destination viewport', () => {
  const args = fixture(), binding = createNativeRunBinding(args)
  const canvas = { width: 700, height: 700, clientWidth: 1000, clientHeight: 1000, devicePixelRatio: 0.7 }
  const state = { ...args.state, nativeViewportBackingPixels: [700, 394], sourceStageViewportBackingPixels: [0, 153, 700, 394],
    sourceStageScissorBackingPixels: [0, 153, 700, 394], destinationCellSourcePixels: [1920 / 1000 * 1000 / 700, 1080 / 562.5 * 1000 / 700] }
  const geometry = createNativeRunRasterGeometry({ binding, state, canvas })
  assert.deepEqual(geometry.sourceGateBackingPixels, [0, 153.125, 700, 393.75])
  assert.deepEqual(geometry.nativeViewportBackingPixels, [0, 0, 700, 394])
  assert.deepEqual(geometry.destinationScissorBackingPixels, [0, 153, 700, 394])
  assert.equal(geometry.drawingBufferHeight, 700)
  assert.equal(geometry.sourceWidth, 1920); assert.equal(geometry.sourceHeight, 1080)
})

test('a resized source canvas or a stale native epoch cannot authorize the old source-pixel map', () => {
  const args = fixture(), binding = createNativeRunBinding(args)
  const canvas = { width: 800, height: 450, clientWidth: 800, clientHeight: 450, devicePixelRatio: 1 }
  const state = { ...args.state, sourceStageViewportBackingPixels: [0, 0, 800, 450], sourceStageScissorBackingPixels: [0, 0, 800, 450],
    destinationCellSourcePixels: [2.4, 2.4] }
  assert.throws(() => createNativeRunRasterGeometry({ binding, state, canvas: { ...canvas, height: 451, clientHeight: 451 } }), /backing viewport.*independently resolved/)
  assert.throws(() => createNativeRunRasterGeometry({ binding, state: { ...state, completedDrawEpoch: 12 }, canvas }), /completed source draw/)
})

test('counterfactual implicit camera centre uses the retained fractional logical ROI, not backing pixels', () => {
  const args = fixture()
  args.view.rectSourcePixels = [...retainedFractionalView.rectSourcePixels]
  args.view.camera = { ...retainedFractionalView.camera }; delete args.view.camera.principalPointViewportPixels
  const layout = sourceLayoutForViews(args.frame.views)
  const runtimeCamera = { ...args.view.camera, principalPointViewportPixels: [240, 44.875] }
  for (const live of [args.state, args.response.actual.views[0], args.response.captures[0].capture, args.response.captures[0].mechanism]) {
    live.sourceLayout = layout; live.rectSourcePixels = args.view.rectSourcePixels
  }
  args.state.nativeViewportBackingPixels = [240, 45]
  args.state.camera = runtimeCamera; args.response.actual.views[0].camera = runtimeCamera
  assert.deepEqual(createNativeRunBinding(args).camera.principalPointViewportPixels, [240, 44.875])
  args.state.camera = { ...runtimeCamera, principalPointViewportPixels: [120, 22.5] }
  assert.throws(() => createNativeRunBinding(args), /native camera differs/)
})

test('retained authored camera PP follows exact readback arithmetic, but a 0.01 source-pixel shift is rejected', () => {
  const args = fixture()
  args.view.rectSourcePixels = [...retainedFractionalView.rectSourcePixels]
  args.view.camera = structuredClone(retainedFractionalView.camera)
  const layout = sourceLayoutForViews(args.frame.views)
  for (const live of [args.state, args.response.actual.views[0], args.response.captures[0].capture, args.response.captures[0].mechanism]) {
    live.sourceLayout = layout; live.rectSourcePixels = args.view.rectSourcePixels
  }
  args.response.actual.views[0].camera = args.view.camera
  // Actual retained Scene capture canonicalizes raw58.33825424201738 by one ulp.
  args.state.camera = { ...args.view.camera, principalPointViewportPixels: [58.33825424201737, 77.46318890942115] }
  assert.deepEqual(createNativeRunBinding(args).camera.principalPointViewportPixels, [58.33825424201738, 77.46318890942115])
  args.state.camera = { ...args.state.camera, principalPointViewportPixels: [58.34825424201737, 77.46318890942115] }
  assert.throws(() => createNativeRunBinding(args), /native camera differs/)
})

test('retained chosen matrix-only page-flip warps cannot impersonate measured homography authority', async () => {
  const legacy = JSON.parse(await readFile(new URL('../content/6dW6VYXp9HM.source-track.json', import.meta.url), 'utf8'))
  const matrixOnlyView = legacy.frames.flatMap(frame => frame.views ?? []).find(view => view.imagePlaneWarp?.renderToSourcePixels
    && !view.imagePlaneWarp.cornersSourcePixels)
  assert.throws(() => sourceLayoutForViews([matrixOnlyView]), /four ordered measured corners/)
})
