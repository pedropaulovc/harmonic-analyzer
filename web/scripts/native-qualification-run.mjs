import { readFile } from 'node:fs/promises'
import { resolve, relative, isAbsolute, sep } from 'node:path'
import { nativeExpectedCameraSnapshot } from '../native-qualification-contract.mjs'
import { CURRENT_NATIVE_RAW_SHA256, CURRENT_NATIVE_DELIVERY_SHA256, CURRENT_NATIVE_DELIVERY_BYTES, canonicalJson, jsonDigest, sha256, requireSHA, integer, parseNativeRawGLB, bindNativeRawPrimitivesToOriginalInventory, createNativeByteReader } from './native-model-byte-proof.mjs'
import { createOriginalNativePoseOracle } from './native-original-cpu.mjs'
import { createNativeQualificationSession, closeNativeCodeManifest } from './native-qualification.mjs'
import { createNativeSourceFeatureBindings } from './native-source-feature-bindings.mjs'
import { CURRENT_CONTENT, VIDEO_IDS, MODEL_COMMIT, MODEL_REPRESENTATION, nativeFrameExposureError, sourceImageError, sourceLayoutForViews, sameSourceLayout, sameResolvedImagePlaneWarp } from './verify-reference.mjs'

const authorizedRuns = new WeakSet()
export function isNativeQualificationRun(value) { return authorizedRuns.has(value) }

const encoder = new TextEncoder()
const clone = value => JSON.parse(canonicalJson(value))
const same = (a, b) => canonicalJson(a) === canonicalJson(b)
const finiteVector = (value, length) => Array.isArray(value) && value.length === length && value.every(Number.isFinite)
function insist(condition, message) { if (!condition) throw new Error(message) }
function freezeResult(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) freezeResult(item)
    Object.freeze(value)
  }
  return value
}
function cameraEquivalent(actual, expected, logicalDimensions, rawMetadata = false) {
  if (!actual || !expected) return false
  const actualSnapshot = nativeExpectedCameraSnapshot(actual, logicalDimensions)
  const near = (a, b) => finiteVector(a, b?.length) && a.every((value, i) => Math.abs(value - b[i]) <= 1e-7)
  return near(actual.positionMetres, expected.positionMetres)
    && (near(actualSnapshot.quaternion, expected.quaternion) || near(actualSnapshot.quaternion, expected.quaternion?.map(value => -value)))
    && Number.isFinite(actual.verticalFovDegrees) && Math.abs(actual.verticalFovDegrees - expected.verticalFovDegrees) <= 1e-7
    && same((rawMetadata ? actualSnapshot : actual).principalPointViewportPixels ?? null, expected.principalPointViewportPixels ?? null)
}
function checkAbort(signal) { signal?.throwIfAborted() }
function confinedPath(root, path) {
  insist(typeof path === 'string' && path.length > 0 && !isAbsolute(path), 'Built asset must have a relative manifest path')
  const file = resolve(root, path), local = relative(root, file)
  insist(local !== '..' && !local.startsWith(`..${sep}`) && !isAbsolute(local), 'Built asset escapes dist root')
  return file
}
/** Independently close the actual dist bytes, not filenames or producer claims.
 * All built JavaScript participates, including independently emitted lazy chunks. */
export async function closeNativeRunCode({ distRoot, serverUrl, builtAssets, originalSceneClosureSHA256, signal }) {
  requireSHA(originalSceneClosureSHA256, 'Admitted original CPU closure')
  insist(Array.isArray(builtAssets) && builtAssets.length > 0, 'Actual built asset manifest required')
  const objects = [], seen = new Set()
  for (const asset of builtAssets.filter(asset => /\.(?:m?js)$/.test(asset.path ?? ''))) {
    checkAbort(signal)
    const url = new URL(asset.path, serverUrl.endsWith('/') ? serverUrl : `${serverUrl}/`).href
    insist(!seen.has(url), 'Duplicate built JavaScript URL'); seen.add(url)
    const bytes = await readFile(confinedPath(distRoot, asset.path))
    requireSHA(asset.sha256, 'Built JavaScript SHA256'); integer(asset.bytes, 'Built JavaScript bytes', 1)
    insist(bytes.byteLength === asset.bytes && sha256(bytes) === asset.sha256, `Actual built JavaScript differs from manifest: ${asset.path}`)
    objects.push({ url, sha256: asset.sha256, byteLength: bytes.byteLength, bytes })
  }
  insist(objects.length > 0, 'Actual built JavaScript closure is absent')
  objects.sort((a, b) => a.url < b.url ? -1 : a.url > b.url ? 1 : 0)
  const manifest = objects.map(({ url, sha256, byteLength }) => ({ url, sha256, byteLength }))
  const codeClosure = { sha256: jsonDigest(manifest), objects, originalSceneClosureSHA256 }
  closeNativeCodeManifest(codeClosure)
  return { codeClosure, manifest }
}
/** Only the independently probed indexed tick is admitted. The authored decimal
 * spelling can identify that exposure, but cannot supply tick/timebase authority. */
export function createNativeRunBinding({ record, frame, view, response, state, codeClosureSHA256 }) {
  const native = record?.native, source = record?.track?.source
  insist(frame?.sourceImage?.pixelFormat === 'bgr8', 'Native qualification requires the strict original BGR8 source image')
  const imageIssue = sourceImageError(frame.sourceImage, source, native)
  insist(!imageIssue, imageIssue ?? 'Invalid original source image')
  const index = frame.sourceImage.frameIndex, issue = nativeFrameExposureError(frame, index, native)
  insist(!issue, issue ?? 'Invalid exact original source exposure')
  insist(native?.observedSha256 === source?.sha256 && source?.videoId === record.id, 'Actual original source probe/model route differs')
  const tick = native.ptsTicks?.[index]
  insist(typeof tick === 'string' && /^\d+$/.test(tick) && typeof native.timeBase === 'string' && /^[1-9]\d*\/[1-9]\d*$/.test(native.timeBase), 'Independently probed native ticks/timebase required')
  insist(Number.isFinite(frame.timeSeconds) && Number.isFinite(frame.decodedTimeSeconds) && Math.abs(frame.timeSeconds - frame.decodedTimeSeconds) <= 0.5, 'Nominal time is not the selected exact original exposure')
  const actual = response?.actual, capture = response?.captures?.find(row => row.viewId === view.id)?.capture
  const mechanism = response?.captures?.find(row => row.viewId === view.id)?.mechanism, rendered = actual?.views?.find(row => row.id === view.id)
  insist(actual?.videoId === record.id && actual.playerVideoId === record.id && actual.mode === 'reference-review' && actual.playerState === 'paused'
    && response.native?.paused === true && response.native.seeking === false && Number.isFinite(response.native.mediaTime), 'Current paused original source-media review required')
  insist(actual.modelTime === frame.timeSeconds && actual.sourceDrawTimeSeconds === frame.timeSeconds, 'Current native draw is not the independently selected nominal source time')
  integer(actual.sourceDrawRevision, 'Current completed source draw revision', 1)
  insist(capture?.status === 'captured' && capture.viewId === view.id && capture.drawRevision === actual.sourceDrawRevision && capture.timeSeconds === frame.timeSeconds
    && mechanism?.status === 'rendered' && mechanism.method === 'actual-native-mechanism-solve' && mechanism.viewId === view.id
    && mechanism.sourceDrawRevision === actual.sourceDrawRevision && mechanism.timeSeconds === frame.timeSeconds, 'Current draw/physical solve/GPU marker receipt differs')
  insist(state?.status === 'captured' && state.viewId === view.id && state.drawRevision === actual.sourceDrawRevision && state.timeSeconds === frame.timeSeconds, 'Native binary state is not from the current source draw')
  integer(state.completedDrawEpoch, 'Actual GPU-completed scene epoch', 1)
  const layout = sourceLayoutForViews(frame.views), resolved = layout.find(row => row.viewId === view.id)?.resolvedImagePlaneWarp
  const logicalViewport = view.imagePlaneWarp?.unwarpedViewportPixels ?? view.rectSourcePixels.slice(2)
  const expectedRuntimeCamera = { ...view.camera, principalPointViewportPixels: view.camera.principalPointViewportPixels ?? logicalViewport.map(value => value / 2) }
  const expectedSnapshot = nativeExpectedCameraSnapshot(expectedRuntimeCamera, logicalViewport)
  insist(rendered && same(rendered.input, view.input) && same(mechanism.input, view.input), 'Actual full physical input differs from independently selected source view')
  insist(cameraEquivalent(rendered.camera, expectedSnapshot, logicalViewport, true) && cameraEquivalent(state.camera, expectedSnapshot, logicalViewport),
    'Actual native camera differs from independent selected camera')
  insist(same(rendered.rectSourcePixels, view.rectSourcePixels) && same(state.rectSourcePixels, view.rectSourcePixels)
    && rendered.presentation === view.presentation && state.presentation === view.presentation, 'Actual view ROI/orientation differs from independently selected source view')
  for (const live of [rendered, mechanism, capture, state]) {
    insist(sameSourceLayout(live.sourceLayout, layout) && sameResolvedImagePlaneWarp(live.resolvedImagePlaneWarp, resolved), 'Current ordered layout/resolved warp differs from independent source view')
  }
  insist(same(rendered.composite ?? { mode: 'opaque' }, view.composite ?? { mode: 'opaque' })
    && same(rendered.compositeProvenance ?? null, view.compositeProvenance ?? null), 'Current composition/provenance differs from independently selected source view')
  requireSHA(codeClosureSHA256, 'Actual built JavaScript closure')
  return clone({ sourceVideoId: record.id, sourceSha256: native.observedSha256, sourceImage: frame.sourceImage,
    decodedFrameIndex: index, decodedTimestampTicks: tick, timeBase: native.timeBase, shotId: frame.shotId, viewId: view.id,
    timeSeconds: frame.timeSeconds, decodedTimeSeconds: frame.decodedTimeSeconds, modelSourceCommit: MODEL_COMMIT,
    modelRawSHA256: CURRENT_NATIVE_RAW_SHA256, modelDeliverySHA256: CURRENT_NATIVE_DELIVERY_SHA256, modelDeliveryByteLength: CURRENT_NATIVE_DELIVERY_BYTES,
    currentBuildClosureSHA256: codeClosureSHA256, input: view.input, inputSHA256: jsonDigest(view.input), camera: expectedRuntimeCamera,
    rectSourcePixels: view.rectSourcePixels, presentation: view.presentation, composite: view.composite ?? { mode: 'opaque' }, compositeProvenance: view.compositeProvenance ?? null,
    imagePlaneWarp: view.imagePlaneWarp ?? null, resolvedImagePlaneWarp: resolved, sourceLayout: layout, partOverrides: view.partOverrides ?? [],
    sourceDrawRevision: actual.sourceDrawRevision, completedSceneDrawEpoch: state.completedDrawEpoch })
}

/** Close the source mapping from the independently read live canvas/state and
 * original BGR image dimensions, never from packet-declared raster fields. */
export function createNativeRunRasterGeometry({ binding, state, canvas }) {
  insist(state?.status === 'captured' && state.viewId === binding.viewId
    && state.drawRevision === binding.sourceDrawRevision && state.completedDrawEpoch === binding.completedSceneDrawEpoch,
  'Raster geometry is not the independently selected completed source draw')
  for (const key of ['width', 'height', 'clientWidth', 'clientHeight']) integer(canvas?.[key], `Actual source canvas ${key}`, 1)
  insist(Number.isFinite(canvas.devicePixelRatio) && canvas.devicePixelRatio > 0, 'Actual source canvas device pixel ratio is absent')
  const pixelRatio = Math.min(canvas.devicePixelRatio, 2)
  insist(canvas.width === Math.floor(canvas.clientWidth * pixelRatio) && canvas.height === Math.floor(canvas.clientHeight * pixelRatio),
    'Actual source canvas backing dimensions differ from the real renderer pixel ratio')
  const sourceWidth = binding.sourceImage?.width, sourceHeight = binding.sourceImage?.height
  integer(sourceWidth, 'Original source image width', 1); integer(sourceHeight, 'Original source image height', 1)
  const native = state.nativeViewportBackingPixels, destination = state.sourceStageViewportBackingPixels, scissor = state.sourceStageScissorBackingPixels
  insist(finiteVector(native, 2) && native.every(value => Number.isInteger(value) && value > 0), 'Actual native backing viewport is absent')
  insist(finiteVector(destination, 4) && destination.every(Number.isInteger) && destination[2] > 0 && destination[3] > 0,
    'Actual source-stage backing viewport is absent')
  insist(finiteVector(scissor, 4) && scissor.every(value => Number.isInteger(value) && value >= 0), 'Actual source-stage backing scissor is absent')
  const gateWidth = Math.min(canvas.clientWidth, canvas.clientHeight * sourceWidth / sourceHeight)
  const gateHeight = gateWidth * sourceHeight / sourceWidth
  const gateX = (canvas.clientWidth - gateWidth) / 2, gateY = (canvas.clientHeight - gateHeight) / 2
  const scaleX = canvas.width / canvas.clientWidth, scaleY = canvas.height / canvas.clientHeight
  const [x, y, width, height] = binding.rectSourcePixels
  const left = gateX + x / sourceWidth * gateWidth, top = gateY + y / sourceHeight * gateHeight
  const roiWidth = width / sourceWidth * gateWidth, roiHeight = height / sourceHeight * gateHeight
  const expectedDestination = [left, canvas.clientHeight - top - roiHeight, roiWidth, roiHeight].map(value => Math.round(value * pixelRatio))
  const clamp = (value, maximum) => Math.max(0, Math.min(maximum, value))
  const x0 = clamp(Math.ceil(left * scaleX - 0.5), canvas.width)
  const x1 = Math.max(x0, clamp(Math.ceil((gateX + (x + width) / sourceWidth * gateWidth) * scaleX - 0.5), canvas.width))
  const topPixel = clamp(Math.ceil(top * scaleY - 0.5), canvas.height)
  const bottomPixel = Math.max(topPixel, clamp(Math.ceil((gateY + (y + height) / sourceHeight * gateHeight) * scaleY - 0.5), canvas.height))
  const expectedScissor = [x0, canvas.height - bottomPixel, x1 - x0, bottomPixel - topPixel]
  const warp = binding.resolvedImagePlaneWarp
  const expectedNative = warp ? warp.unwarpedViewportPixels.map(Math.ceil)
    : binding.presentation === 'horizontal-mirror' ? [gateWidth, gateHeight].map(value => Math.max(1, Math.round(value * pixelRatio)))
      : expectedDestination.slice(2)
  insist(same(destination, expectedDestination) && same(scissor, expectedScissor) && same(native, expectedNative),
    'Actual native/source backing viewport or half-open scissor differs from independently resolved source ROI')
  const destinationCellSourcePixels = [sourceWidth / gateWidth * canvas.clientWidth / canvas.width,
    sourceHeight / gateHeight * canvas.clientHeight / canvas.height]
  insist(same(state.destinationCellSourcePixels, destinationCellSourcePixels), 'Actual source-cell mapping differs from original image and live canvas')
  return {
    nativeViewportBackingPixels: [0, 0, ...native],
    destinationViewportBackingPixels: [...destination], destinationScissorBackingPixels: [...scissor],
    destinationCellSourcePixels, sourceGateBackingPixels: [gateX * scaleX, (canvas.clientHeight - gateY - gateHeight) * scaleY,
      gateWidth * scaleX, gateHeight * scaleY],
    drawingBufferHeight: canvas.height, sourceWidth, sourceHeight,
  }
}
async function readLiveFrame(page, viewId) {
  return page.evaluate(id => {
    const bridge = window.harmonicAnalyzer
    if (!bridge?.nativeQualificationState) throw new Error('Native qualification browser bridge is unavailable')
    const canvas = document.querySelector('#stage')
    if (!(canvas instanceof HTMLCanvasElement)) throw new Error('Actual source-stage canvas is unavailable')
    return { actual: bridge.snapshot(), captures: [{ viewId: id, capture: bridge.renderedLandmarks(id), mechanism: bridge.renderedMechanism(id) }], state: bridge.nativeQualificationState(id),
      canvas: { width: canvas.width, height: canvas.height, clientWidth: canvas.clientWidth, clientHeight: canvas.clientHeight, devicePixelRatio } }
  }, viewId)
}
async function readLiveMedia(page, record) {
  const selectors = [{ frame: page, selector: '#video-player video' }]
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue
    let url
    try { url = new URL(frame.url()) } catch { continue }
    if (/(^|\.)youtube(?:-nocookie)?\.com$/.test(url.hostname) && url.pathname === `/embed/${record.id}`) selectors.push({ frame, selector: '#movie_player video.html5-main-video' })
  }
  const media = []
  for (const item of selectors) {
    const current = await item.frame.evaluate(selector => {
      const video = document.querySelector(selector), player = document.querySelector('#movie_player')
      if (!(video instanceof HTMLVideoElement)) return null
      return { present: true, paused: video.paused, seeking: video.seeking, ended: video.ended, mediaTime: video.currentTime,
        duration: video.duration, readyState: video.readyState, width: video.videoWidth, height: video.videoHeight,
        adShowing: !!player?.classList.contains('ad-showing'), error: video.error?.message ?? null, currentSrc: video.currentSrc }
    }, item.selector)
    if (current) media.push(current)
  }
  insist(media.length === 1, 'Actual unique original source media element is absent or ambiguous')
  const current = media[0]
  insist(current.paused && !current.seeking && !current.error && !current.adShowing && current.readyState >= 2 && current.width > 0 && current.height > 0
    && Number.isFinite(current.mediaTime) && Number.isFinite(current.duration) && Math.abs(current.duration - record.native.durationSeconds) <= 1, 'Actual original source media changed or is not decoded/paused')
  return current
}
function directObjectReferences(value, hashes) {
  if (!value || typeof value !== 'object') return
  if (typeof value.objectSHA256 === 'string') { requireSHA(value.objectSHA256, 'Native binary object'); hashes.add(value.objectSHA256) }
  if (Array.isArray(value.materialSlotsSHA256)) for (const hash of value.materialSlotsSHA256) { requireSHA(hash, 'Material descriptor object'); hashes.add(hash) }
  for (const child of Object.values(value)) directObjectReferences(child, hashes)
}
/** Retain/release the real nested CAS objects, not only the JSON receipt shell. */
export async function nativeReceiptObjects(receipt, byteStore) {
  const reader = createNativeByteReader(byteStore), hashes = new Set(), jsonObjects = new Set()
  for (const key of ['staticNativeSHA256', 'drawableStateSHA256']) { requireSHA(receipt[key], key); hashes.add(receipt[key]); jsonObjects.add(receipt[key]) }
  directObjectReferences(receipt, hashes)
  const visit = async hash => {
    const object = await reader.json(hash), found = new Set()
    directObjectReferences(object, found)
    for (const ref of found) hashes.add(ref)
    if (Array.isArray(object)) for (const row of object) for (const material of row.materialSlotsSHA256 ?? []) {
      if (!jsonObjects.has(material)) { jsonObjects.add(material); await visit(material) }
    }
    if (typeof object.codeObjectSHA256 === 'string') { hashes.add(object.codeObjectSHA256); jsonObjects.add(object.codeObjectSHA256); await reader.object(object.codeObjectSHA256) }
  }
  for (const hash of [...jsonObjects]) await visit(hash)
  return hashes
}
async function pinBytes(byteStore, bytes, retention, expected = sha256(bytes)) {
  const result = await byteStore.put(bytes, { retention })
  insist(result?.sha256 === expected && result.byteLength === bytes.byteLength, 'Native CAS did not store the independently supplied actual bytes')
  await byteStore.retain(expected)
  return expected
}
async function readSourceInspection(webRoot, byteStore) {
  const path = resolve(webRoot, '.vite/verification-output/v39-source-feature-20261003/intro809-source-inspection.json')
  let bytes
  try { bytes = await readFile(path) } catch (error) { if (error.code === 'ENOENT') return null; throw error }
  const inspection = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
  insist(inspection.kind === 'actual-original-decoded-source-raster-inspection', 'Actual primary Intro source inspection has a different kind')
  await pinBytes(byteStore, bytes, 'reference')
  for (const path of inspection.outputs ?? []) {
    insist(typeof path === 'string' && /intro809-(?:source|four-head-source-crops)\.png$/.test(path), 'Primary source inspection points to an unsupported crop artifact')
    const local = resolve(webRoot, '.vite/verification-output/v39-source-feature-20261003', path.split('/').at(-1))
    await pinBytes(byteStore, await readFile(local), 'reference')
  }
  return inspection
}

/** Run-owned Node/browser loop. The caller supplies an independently ADMITTED
 * original CPU closure and pinned protected spring oracle; neither is regenerated
 * from current source. enableOptionsFor(record) supplies route-scoped original
 * markers to the opt-in bridge. The existing paused seek/review is unchanged.
 *
 * Gate callers first require isNativeQualificationRun(run), then exact private
 * frame/adjudication membership and the independent source/body tuple. The frozen
 * API cannot be copied or have authority callbacks replaced to mint evidence.
 *
 * A rejected late context may retain capturedCounterexample for an actual failed
 * Node result bound to its original verified pre-Consumer tuple. It cannot pass
 * current qualification or be retagged to a later draw/source row.
 *
 * Results keep the Consumer's exact private-WeakSet adjudications. Source losses,
 * original roles and moving/CHECK gaps remain a separate ledger, never implied by
 * a successful native-program or material qualification. dispose releases this
 * session/oracle only; the caller owns the byte store and server lifecycle. */
export async function createNativeQualificationRun({ webRoot, distRoot, serverUrl, byteStore, builtAssets, originalCPUClosure, originalSpringOraclePath, originalSpringOracleSHA256, signal }) {
  insist(typeof webRoot === 'string' && typeof distRoot === 'string' && typeof serverUrl === 'string', 'Explicit web/dist/server roots required')
  insist(byteStore?.get && byteStore.put && byteStore.retain && byteStore.release && typeof byteStore.endpoint === 'string', 'Actual asynchronous native CAS with HTTP endpoint required')
  insist(originalCPUClosure?.manifest && originalCPUClosure.modules && originalCPUClosure.manifestSHA256, 'Independently admitted original CPU closure must be explicitly supplied; no current-source fallback')
  requireSHA(originalCPUClosure.manifestSHA256, 'Admitted original CPU closure SHA256')
  requireSHA(originalSpringOracleSHA256, 'Independently pinned protected original spring oracle SHA256')
  insist(typeof originalSpringOraclePath === 'string' && originalSpringOraclePath.length > 0, 'Protected original spring oracle path required')
  checkAbort(signal)
  const rawGLBBytes = await readFile(resolve(webRoot, `.vite/model-source/${CURRENT_NATIVE_RAW_SHA256}.glb`))
  const deliveryGLBBytes = await readFile(confinedPath(distRoot, MODEL_REPRESENTATION.representation.path))
  const oracleBytes = await readFile(originalSpringOraclePath)
  insist(sha256(rawGLBBytes) === CURRENT_NATIVE_RAW_SHA256 && sha256(deliveryGLBBytes) === CURRENT_NATIVE_DELIVERY_SHA256
    && deliveryGLBBytes.byteLength === CURRENT_NATIVE_DELIVERY_BYTES, 'Actual immutable raw/delivery model bytes differ from CURRENT462')
  insist(sha256(oracleBytes) === originalSpringOracleSHA256, 'Actual protected original spring oracle bytes differ from independent pin')
  const { codeClosure, manifest: codeManifest } = await closeNativeRunCode({ distRoot, serverUrl, builtAssets, originalSceneClosureSHA256: originalCPUClosure.manifestSHA256, signal })
  const rawHashes = new Set()
  for (const bytes of [rawGLBBytes, deliveryGLBBytes, oracleBytes]) rawHashes.add(await pinBytes(byteStore, bytes, 'reference'))
  for (const object of codeClosure.objects) rawHashes.add(await pinBytes(byteStore, object.bytes, 'static', object.sha256))
  const codeObjectSHA256 = await pinBytes(byteStore, encoder.encode(canonicalJson(codeManifest)), 'static', codeClosure.sha256)
  const originalManifestSHA256 = await pinBytes(byteStore, encoder.encode(canonicalJson(originalCPUClosure.manifest)), 'reference', originalCPUClosure.manifestSHA256)
  for (const module of originalCPUClosure.modules) for (const bytes of [module.source, module.transformed]) {
    insist(bytes instanceof Uint8Array, 'Original retained CPU source/executable bytes required')
    const hash = sha256(bytes)
    if (!rawHashes.has(hash)) { await pinBytes(byteStore, bytes, 'reference', hash); rawHashes.add(hash) }
  }
  let poseOracle, session
  try {
    poseOracle = await createOriginalNativePoseOracle({ closure: originalCPUClosure })
    const parsed = parseNativeRawGLB(rawGLBBytes), nativeModel = { ...parsed, rawSHA256: CURRENT_NATIVE_RAW_SHA256 }
    nativeModel.primitives = bindNativeRawPrimitivesToOriginalInventory(nativeModel, poseOracle.inventory)
    const sourceInspection = await readSourceInspection(webRoot, byteStore)
    const sourceFeatures = createNativeSourceFeatureBindings({ nativeModel, poseOracle, sourceInspection })
    session = await createNativeQualificationSession({ byteStore, rawGLBBytes, deliveryGLBBytes, codeClosure, poseOracle, originalSpringOraclePath, originalSpringOracleSHA256 })
    const rawDrawables = poseOracle.inventory.drawables.map(entry => {
      const primitive = nativeModel.primitives.get(entry.path)
      return { path: entry.path, nodeIndex: primitive.nodeIndex, meshIndex: primitive.meshIndex, primitiveIndex: primitive.primitiveIndex, instanceOf: primitive.instanceOf }
    })
    const sinkEndpoint = new URL(byteStore.endpoint, serverUrl).href
    const captureContext = { codeClosureSHA256: codeClosure.sha256, rawDrawables, rawCaseRetention: 'streamed-live-only',
      cameraOutputCapture: 'finite-linear-enclosure', consumerVerifiedPhysicalStates: [] }
    const selected = new Set(), epochs = new Map(), consumerVerifiedPhysicalStates = new Set(), pendingPhysicalAcknowledgements = new Set(), referenceRecords = new Map()
    const authorizedFrames = new WeakSet()
    let disposed = false, queue = Promise.resolve(), acknowledgementVideoId = null
    async function admitRecord(record) {
      insist(VIDEO_IDS.includes(record.id), 'Native qualification needs an original source video identity')
      let admitted = referenceRecords.get(record.id)
      if (!admitted) {
        const records = {}
        for (const [name, suffix] of [['observations', 'observations'], ['track', 'source-track']]) {
          const bytes = await readFile(resolve(webRoot, `${CURRENT_CONTENT}/${record.id}.${suffix}.json`))
          records[name] = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
          insist(same(records[name], record[name]), `Supplied ${name} differs from actual retained original source/code-selection bytes`)
          await pinBytes(byteStore, bytes, 'reference')
        }
        await pinBytes(byteStore, encoder.encode(canonicalJson(record.native)), 'reference')
        admitted = { ...record, ...records, native: clone(record.native) }
        referenceRecords.set(record.id, admitted)
      }
      insist(record.digest === jsonDigest(admitted.track) && same(record.native, admitted.native), 'Original source/reference authority changed during native qualification')
      return admitted
    }
    async function qualifyFrame({ page, record, frame, response, required = true, readMedia = () => readLiveMedia(page, record) }) {
      insist(!disposed, 'Native qualification run is disposed'); checkAbort(signal)
      const admitted = await admitRecord(record)
      const views = [], sourceUnavailable = clone([
        ...(Array.isArray(frame?.unavailable) ? frame.unavailable : frame?.unavailable == null ? [] : [frame.unavailable]),
        ...(frame?.sourceUnavailable ?? []), ...(frame?.contourJoinUnavailable ?? []),
      ])
      for (const view of frame?.views ?? []) {
        let receipt, adjudication, capturedBinding, objectHashes, retention = null
        const unavailable = []
        try {
          checkAbort(signal)
          const before = await readLiveFrame(page, view.id), mediaBefore = await readMedia()
          const originalBinding = createNativeRunBinding({ record: admitted, frame, view, response, state: before.state, codeClosureSHA256: codeClosure.sha256 })
          const liveBinding = createNativeRunBinding({ record: admitted, frame, view, response: { ...before, native: mediaBefore }, state: before.state, codeClosureSHA256: codeClosure.sha256 })
          insist(same(originalBinding, liveBinding), 'Source/physical draw changed since the actual reviewed response')
          insist(mediaBefore.mediaTime === response.native.mediaTime && Math.abs(mediaBefore.mediaTime - frame.decodedTimeSeconds) <= 0.5, 'Actual paused original exposure changed before native capture')
          const epochKey = `${record.id}/${view.id}`, prior = epochs.get(epochKey)
          insist(!prior || liveBinding.completedSceneDrawEpoch >= prior.epoch, 'Native GPU completed epoch regressed')
          if (prior?.epoch === liveBinding.completedSceneDrawEpoch) insist(prior.bindingSHA256 === jsonDigest(liveBinding), 'One completed epoch was rebound to a different independent source tuple')
          const rasterGeometry = createNativeRunRasterGeometry({ binding: liveBinding, state: before.state, canvas: before.canvas })
          const expected = sourceFeatures.forView({ record: admitted, frame, view, binding: liveBinding, viewport: before.state.nativeViewportBackingPixels })
          unavailable.push(...expected.unavailable)
          const primaryFeatureCase = sourceFeatures.featureMarkers.some(marker => marker.sourceVideoId === record.id && marker.timeSeconds === frame.timeSeconds && marker.viewId === view.id)
          const selectedKey = primaryFeatureCase ? `${record.id}/primary-feature/${frame.sourceImage.frameIndex}/${view.id}` : `${record.id}/${frame.shotId}/${view.id}`
          const keep = !selected.has(selectedKey), acknowledgementDelta = [...pendingPhysicalAcknowledgements]
          const context = { ...captureContext, rawCaseRetention: keep ? 'retained-selected-case' : 'streamed-live-only',
            cameraOutputCapture: keep ? 'selected-measured-tf' : 'finite-linear-enclosure', consumerVerifiedPhysicalStates: acknowledgementDelta }
          receipt = await page.evaluate(request => window.harmonicAnalyzer.captureNativeQualification(request), { binding: liveBinding, sinkEndpoint, context })
          for (const key of acknowledgementDelta) pendingPhysicalAcknowledgements.delete(key)
          // The upload/capture await can run script or receive media events. Re-read
          // real current source/physical/GPU state before admitting ANY packet.
          const after = await readLiveFrame(page, view.id), mediaAfter = await readMedia()
          const afterBinding = createNativeRunBinding({ record: admitted, frame, view, response: { ...after, native: mediaAfter }, state: after.state, codeClosureSHA256: codeClosure.sha256 })
          insist(same(liveBinding, afterBinding) && mediaAfter.mediaTime === mediaBefore.mediaTime && mediaAfter.currentSrc === mediaBefore.currentSrc, 'Native capture became stale during asynchronous binary upload')
          insist(same(rasterGeometry, createNativeRunRasterGeometry({ binding: afterBinding, state: after.state, canvas: after.canvas })),
            'Source raster geometry changed during asynchronous binary upload')
          // Receipt status/max/pass are never authority. The Consumer gets actual
          // original source facts and independent binding plus all current bytes.
          capturedBinding = freezeResult(clone(liveBinding))
          adjudication = await session.qualifyDraw(receipt, { binding: liveBinding, witnesses: expected.witnesses,
            sourceFrame: expected.sourceFrame, sourceView: expected.sourceView, bodyProof: expected.bodyProof, rawCaseRetention: context.rawCaseRetention,
            cameraOutputCapture: context.cameraOutputCapture, rasterGeometry, sourceVisibilityProof: expected.sourceVisibilityProof,
            sourceRuntimeWitness: expected.sourceRuntimeWitness, sourceMechanicalStateStatus: expected.sourceMechanicalStateStatus,
            expectedVisibilityBinding: expected.expectedVisibilityBinding, sourceVisibilityErrors: expected.sourceVisibilityErrors,
            sourceOriginalData: expected.sourceOriginalData, allCurrent462Census: expected.allCurrent462Census })
          insist(session.isAdjudication(adjudication), 'Native result is not the real byte Consumer adjudication')
          insist(Array.isArray(adjudication.nativePhysicalCacheKeys) && Array.isArray(adjudication.features), 'Actual Consumer cache/feature contract is incomplete')
          insist(['qualified', 'unmeasured', 'failed'].includes(adjudication.sourceBodyEligibility?.status), 'Actual Consumer full source-body eligibility contract is incomplete')
          for (const key of adjudication.nativePhysicalCacheKeys) {
            requireSHA(key, 'Actual Consumer-computed physical cache key')
            if (!consumerVerifiedPhysicalStates.has(key)) { consumerVerifiedPhysicalStates.add(key); pendingPhysicalAcknowledgements.add(key) }
          }
          objectHashes = await nativeReceiptObjects(receipt, byteStore)
          const retain = keep
          const receiptSHA256 = await pinBytes(byteStore, encoder.encode(canonicalJson(receipt)), retain ? 'selected-case' : 'reference')
          if (retain) {
            for (const hash of objectHashes) await byteStore.retain(hash)
            selected.add(selectedKey)
            retention = { rawCaseRetention: 'retained-selected-case', receiptSHA256, objectCount: objectHashes.size, reason: 'selected-original-view-case' }
          } else {
            // Only AFTER complete Consumer computation/cache may live numeric,
            // matrix and raster spans be dropped. Static pins survive release.
            for (const hash of objectHashes) await byteStore.release(hash)
            retention = { rawCaseRetention: 'streamed-live-only', receiptSHA256, objectCount: objectHashes.size, reason: 'released-after-actual-node-adjudication',
              consumerStatus: adjudication.status }
          }
          const settled = await readLiveFrame(page, view.id), mediaSettled = await readMedia()
          const settledBinding = createNativeRunBinding({ record: admitted, frame, view, response: { ...settled, native: mediaSettled }, state: settled.state, codeClosureSHA256: codeClosure.sha256 })
          insist(same(liveBinding, settledBinding) && mediaSettled.mediaTime === mediaBefore.mediaTime && mediaSettled.currentSrc === mediaBefore.currentSrc,
            'Native draw/source context changed while Node adjudicated or retained actual bytes')
          insist(same(rasterGeometry, createNativeRunRasterGeometry({ binding: settledBinding, state: settled.state, canvas: settled.canvas })),
            'Source raster geometry changed while Node adjudicated or retained actual bytes')
          epochs.set(epochKey, { epoch: liveBinding.completedSceneDrawEpoch, bindingSHA256: jsonDigest(liveBinding) })
          views.push({ viewId: view.id, required, adjudication, features: adjudication.features, sourceBodyEligibility: adjudication.sourceBodyEligibility,
            sourceUnavailable: unavailable, retention })
        } catch (error) {
          if (signal?.aborted) throw signal.reason
          // Capture/retention failures remain visible; a packet's selected label
          // never implies that all bytes were in fact retained by Node.
          unavailable.push({ viewId: view.id, status: 'unmeasured-native', reason: error.message })
          if (receipt && retention === null) {
            try {
              const receiptSHA256 = await pinBytes(byteStore, encoder.encode(canonicalJson(receipt)), 'selected-case')
              objectHashes ??= await nativeReceiptObjects(receipt, byteStore)
              for (const hash of objectHashes) await byteStore.retain(hash)
              retention = { rawCaseRetention: 'retained-selected-case', receiptSHA256, objectCount: objectHashes.size, reason: 'rejected-live-context-case' }
            } catch (retentionError) { retention = { rawCaseRetention: 'retention-incomplete', reason: retentionError.message } }
          }
          const capturedCounterexample = adjudication?.status === 'failed' && session.isAdjudication(adjudication)
            && capturedBinding && adjudication.bindingSHA256 === jsonDigest(capturedBinding)
            ? freezeResult({ binding: capturedBinding, adjudication }) : null
          views.push({ viewId: view.id, required, adjudication: null, rejectedAdjudication: adjudication ?? null,
            capturedCounterexample, features: [], sourceUnavailable: unavailable, retention })
        }
        sourceUnavailable.push(...unavailable)
      }
      if (!(frame?.views?.length > 0)) sourceUnavailable.push({ status: 'unmeasured-native', reason: 'Required source frame has no actual native views' })
      const nativeStatus = views.length && views.every(view => view.adjudication?.status === 'qualified') ? 'qualified'
        : views.some(view => view.adjudication?.status === 'failed') ? 'failed' : 'unmeasured'
      const sourceBodyStatus = views.length && views.every(view => view.sourceBodyEligibility?.status === 'qualified') ? 'qualified'
        : views.some(view => view.sourceBodyEligibility?.status === 'failed') ? 'failed' : 'unmeasured'
      const result = freezeResult({ schemaVersion: 1, sourceVideoId: record.id, sourceImage: frame.sourceImage ? clone(frame.sourceImage) : null,
        timeSeconds: frame.timeSeconds, shotId: frame.shotId, required, views, sourceUnavailable, nativeStatus, sourceBodyStatus,
        status: nativeStatus === 'failed' || sourceBodyStatus === 'failed' ? 'failed'
          : nativeStatus === 'qualified' && sourceBodyStatus === 'qualified' && !sourceUnavailable.length ? 'qualified' : 'unmeasured' })
      authorizedFrames.add(result)
      return result
    }
    const run = freezeResult({
      sinkEndpoint, captureContext, featureMarkers: sourceFeatures.featureMarkers,
      enableOptionsFor(record) {
        insist(VIDEO_IDS.includes(record?.id), 'Original source video identity required for native marker admission')
        if (acknowledgementVideoId !== record.id) { consumerVerifiedPhysicalStates.clear(); pendingPhysicalAcknowledgements.clear(); acknowledgementVideoId = record.id }
        return { featureMarkers: sourceFeatures.featureMarkers.filter(marker => marker.sourceVideoId === record.id) }
      },
      configuration: { codeClosureSHA256: codeClosure.sha256, codeManifest, codeObjectSHA256, originalSceneClosureSHA256: originalCPUClosure.manifestSHA256,
        originalManifestSHA256, originalSpringOracleSHA256, modelRawSHA256: CURRENT_NATIVE_RAW_SHA256, modelDeliverySHA256: CURRENT_NATIVE_DELIVERY_SHA256,
        modelDeliveryByteLength: CURRENT_NATIVE_DELIVERY_BYTES, sourceInspectionAvailable: sourceInspection !== null },
      qualifyFrame(args) { const result = queue.then(() => qualifyFrame(args)); queue = result.then(() => undefined, () => undefined); return result },
      isAdjudication: result => session.isAdjudication(result),
      isFrameQualification: result => authorizedFrames.has(result),
      async dispose() { if (disposed) return; disposed = true; await queue; session.dispose(); poseOracle.dispose() },
    })
    authorizedRuns.add(run)
    return run
  } catch (error) { session?.dispose(); poseOracle?.dispose(); throw error }
}
