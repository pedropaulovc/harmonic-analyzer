import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { validateModelRepresentation, assertNativeSourceAssociation } from '../model-representation.mjs'
import { nativeProvenanceFromModule } from './fetch-model.mjs'
import { loadNativeIdentityMap } from './native-identity-map.mjs'
import { VIDEO_IDS, INPUT_FIELDS, completeInput, canonicalJson, sourceImageError, sourceNeedsMachine, recomputeImagePlaneWarp, sameResolvedImagePlaneWarp, nativeLineAxisGeometryBound, nativeGeometryAssumptionErrors, runTool } from './verify-reference.mjs'

export const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
export const FRESH_DIRECTORY = 'content/v39-source'
export const INVENTORY_PATH = 'web/content/v39-source/native-inventory.json'
const finite = value => typeof value === 'number' && Number.isFinite(value)
const vector = (value, size) => Array.isArray(value) && value.length === size && value.every(finite)
const text = value => typeof value === 'string' && Boolean(value.trim())
const hash = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
const equal = (a, b) => canonicalJson(a) === canonicalJson(b)
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const CLASSIFICATIONS = ['machine', 'non-machine', 'transition', 'unobservable']
const LEGACY_FIELDS = new Set(['identityDerivative', 'runtimeWitness', 'sourceCameraRigs', 'sharedRigValidation', 'registrationValidation', 'archivedNativeBindings', 'visibilityProof', 'partOverrides', 'cameraEvidence', 'mechanicalState', 'sourceNonIdentifiableFixedParts'])
const FRESH_SCHEMA = JSON.parse(await readFile(
  resolve(WEB_ROOT, 'scripts/fresh-source-observations.schema.json'), 'utf8'))
const CURRENT_VIEW_FIELDS = new Set(Object.keys(FRESH_SCHEMA.$defs.view.properties))
const CURRENT_ANCHOR_FIELDS = new Set(Object.keys(FRESH_SCHEMA.$defs.anchor.properties))

function rejectLegacy(value) {
  if (!value || typeof value !== 'object') return
  for (const [key, child] of Object.entries(value)) {
    if (LEGACY_FIELDS.has(key)) {
      throw Object.assign(new Error(`Historical/native receipt field is not current source evidence: ${key}`),
        { code: 'historical-source-evidence', field: key })
    }
    rejectLegacy(child)
  }
}

/** Re-read live authority and the independently registered actual exporter bytes on every call. */
export async function loadCurrentAuthority(webRoot = WEB_ROOT) {
  const approved = validateModelRepresentation(JSON.parse(await readFile(resolve(webRoot, 'content/model-representation.json'), 'utf8')))
  const native = nativeProvenanceFromModule(await readFile(resolve(webRoot, 'src/mechanics-data.ts'), 'utf8'))
  assertNativeSourceAssociation(approved, native)
  await loadNativeIdentityMap()
  const manifest = JSON.parse(await readFile(resolve(webRoot, 'content/canonical-native/manifest.json'), 'utf8'))
  const seal = manifest.currentSourceInventory
  assert(seal?.path === INVENTORY_PATH && hash(seal.sha256), 'Current actual native inventory has not been independently registered')
  const raw = await readFile(resolve(webRoot, 'content/v39-source/native-inventory.json'))
  assert(digest(raw) === seal.sha256, 'Current actual native inventory bytes differ from their independent seal')
  const inventory = JSON.parse(raw)
  assert(inventory.sha256 === approved.source.sha256 && equal(inventory.source, approved.source)
    && equal(inventory.identity, approved.identity), 'Actual inventory source/map/canonical tuple differs from live approval')
  assert(inventory.matrixConvention === 'column-major part-local-metres to native-world-metres', 'Current inventory matrix convention differs')
  const census = inventory.census, rows = inventory.inventory
  assert(Array.isArray(rows) && rows.length > 0 && census?.releasedDescendantRestMatrixCount === rows.length
    && census.artifactNodeCount === approved.identity.nodeCount && census.nativeRootCount === 1
    && census.artifactDrawableCount === approved.equivalence.drawableCount
    && Number.isSafeInteger(census.releasedMeshNodeCount) && census.releasedMeshNodeCount > 0
    && census.releasedNonMeshTransformCount === rows.length - census.releasedMeshNodeCount
    && rows.length + census.nativeRootCount + census.nonNativeNodeCount === census.artifactNodeCount
    && census.instanceScope === 'released-native-descendants', 'Actual native inventory census differs')
  const paths = new Set()
  for (const row of rows) {
    assert(typeof row.path === 'string' && /^ha-harmonic-analyzer\/[^/*?]+(?:\/[^/*?]+)*$/.test(row.path)
      && !paths.has(row.path) && text(row.sourcePath) && vector(row.world, 16)
      && equal([row.world[3], row.world[7], row.world[11], row.world[15]], [0, 0, 0, 1]), 'Actual inventory has an invalid or duplicate canonical transform')
    paths.add(row.path)
  }
  // These are renderer-created bodies sharing one decoded native template, not
  // invented released inventory/REST rows. Execute the sole creation ledger.
  const runtimeInstances = await withCurrentRuntime(webRoot, async server => {
    const { NATIVE_RUNTIME_INSTANCES } = await server.ssrLoadModule('/src/source-assembly.ts')
    assert(NATIVE_RUNTIME_INSTANCES && equal(Object.keys(NATIVE_RUNTIME_INSTANCES).sort(), ['crankMedium', 'upperMedium']),
      'Current runtime instance creation ledger must declare exactly its two genuine roles')
    const instances = new Map(), templates = new Set()
    for (const row of Object.values(NATIVE_RUNTIME_INSTANCES)) {
      assert(row && equal(Object.keys(row).sort(), ['localGeometryBinding', 'partPath', 'templatePartPath'])
        && text(row.partPath) && !paths.has(row.partPath) && !instances.has(row.partPath)
        && paths.has(row.templatePartPath)
        && row.localGeometryBinding === 'shared-decoded-native-template-attributes-and-index',
      'Current runtime instance ledger differs from the approved raw native template binding')
      instances.set(row.partPath, row)
      templates.add(row.templatePartPath)
    }
    assert(templates.size === 1, 'Current runtime instances must share the one genuine released template')
    return instances
  })
  // The catalog is a separate original-source oracle, not supplied by the annotation.
  const catalog = await readFile(resolve(webRoot, 'src/video-catalog.ts'), 'utf8')
  const videos = new Map([...catalog.matchAll(/id: '([^']+)'[^\n]*durationSeconds: ([0-9.]+), sourceSha256: '([a-f0-9]{64})'/g)]
    .map(match => [match[1], { durationSeconds: Number(match[2]), sha256: match[3] }]))
  assert(videos.size === VIDEO_IDS.length && VIDEO_IDS.every(id => videos.has(id)), 'Original-source catalog census differs')
  return { approved, inventory, inventorySha256: seal.sha256, paths, runtimeInstances, videos }
}

function validateCurrentAnchors(data, authority) {
  assert(Array.isArray(data.anchors), 'Current native anchor census is missing')
  const anchors = new Map()
  for (const anchor of data.anchors) {
    assert(anchor && Object.keys(anchor).every(key => CURRENT_ANCHOR_FIELDS.has(key))
      && text(anchor.id) && !anchors.has(anchor.id) && ['section-center', 'physical-feature'].includes(anchor.kind)
      && text(anchor.description) && text(anchor.correspondenceEvidence)
      && (Object.hasOwn(anchor, 'worldMetres') !== Object.hasOwn(anchor, 'partLocalMetres'))
      && vector(anchor.worldMetres ?? anchor.partLocalMetres, 3), 'Current anchor lacks a closed actual native feature association')
    const instance = authority.runtimeInstances.get(anchor.partPath)
    if (instance) {
      assert(anchor.runtimeTemplatePartPath === instance.templatePartPath
        && Object.hasOwn(anchor, 'partLocalMetres') && !Object.hasOwn(anchor, 'worldMetres'),
      'Runtime instance anchor needs its exact declared native template and part-local feature; no instance REST/world anchor is available')
    } else {
      assert(authority.paths.has(anchor.partPath) && !Object.hasOwn(anchor, 'runtimeTemplatePartPath'),
        'Current anchor references an unknown runtime instance/alias or mislabels a released native part as a template instance')
    }
    anchors.set(anchor.id, anchor)
  }
  return anchors
}

function unavailable(value) {
  return Array.isArray(value) && value.length > 0 && value.every(row => row && text(row.reason))
}
function requireCamera(camera, label) {
  assert(vector(camera?.positionMetres, 3) && vector(camera.quaternion, 4)
    && Math.abs(Math.hypot(...camera.quaternion) - 1) <= 0.002
    && finite(camera.verticalFovDegrees) && camera.verticalFovDegrees > 0 && camera.verticalFovDegrees < 179
    && (camera.principalPointViewportPixels === undefined || vector(camera.principalPointViewportPixels, 2)), `${label}: invalid current camera`)
}

function validateWarp(measurement, frame, view, frames, label) {
  assert(measurement && equal(measurement.sourceImage, frame.sourceImage)
    && !sourceImageError(measurement.referenceSourceImage, null)
    && vector(measurement.unwarpedViewportPixels, 2), `${label}: warp lacks actual target/reference exposure`)
  const parents = frames.filter(row => equal(row.sourceImage, measurement.referenceSourceImage))
    .flatMap(row => row.views.filter(parent => parent.id === view.id))
  assert(parents.length > 0 && parents.every(parent => parent.presentation === view.presentation
    && equal(parent.rectSourcePixels, parents[0].rectSourcePixels)), `${label}: warp reference has no unambiguous independently observed current layout`)
  const referenceRect = parents[0].rectSourcePixels
  const scale = measurement.unwarpedViewportPixels[0] / referenceRect[2]
  assert(scale > 0 && Math.abs(measurement.unwarpedViewportPixels[1] / referenceRect[3] - scale) <= 1e-9 * Math.max(1, scale),
    `${label}: warp reference aspect differs`)
  const bound = evidence => evidence && equal(evidence.sourceImage, frame.sourceImage)
    && equal(evidence.referenceSourceImage, measurement.referenceSourceImage) && text(evidence.evidence)
  assert(bound(measurement.cornerMeasurementEvidence), `${label}: warp corners lack independent source measurement evidence`)
  const resolved = recomputeImagePlaneWarp(measurement)
  assert(sameResolvedImagePlaneWarp(view.imagePlaneWarp, resolved), `${label}: warp matrix differs from independently measured corners`)
  const ids = new Set(), references = new Set(), pixels = new Set(), checks = []
  assert(Array.isArray(measurement.correspondences), `${label}: warp interior observations are missing`)
  for (const item of measurement.correspondences) {
    assert(text(item.id) && !ids.has(item.id) && ['fit', 'check'].includes(item.role)
      && ['manual', 'optical-flow', 'image-edge', 'template-match'].includes(item.method)
      && vector(item.referencePixelSource, 2) && vector(item.pixelSource, 2)
      && item.referencePixelSource[0] >= referenceRect[0] && item.referencePixelSource[0] < referenceRect[0] + referenceRect[2]
      && item.referencePixelSource[1] >= referenceRect[1] && item.referencePixelSource[1] < referenceRect[1] + referenceRect[3]
      && item.pixelSource[0] >= 0 && item.pixelSource[0] < 1920 && item.pixelSource[1] >= 0 && item.pixelSource[1] < 1080
      && finite(item.uncertaintyPx) && item.uncertaintyPx >= 0 && bound(item.measurementEvidence)
      && !references.has(canonicalJson(item.referencePixelSource)) && !pixels.has(canonicalJson(item.pixelSource)),
    `${label}: warp FIT/CHECK features are not independent actual source observations`)
    ids.add(item.id); references.add(canonicalJson(item.referencePixelSource)); pixels.add(canonicalJson(item.pixelSource))
    if (item.role === 'check') {
      assert(item.referencePixelSource[0] > referenceRect[0] && item.referencePixelSource[0] < referenceRect[0] + referenceRect[2]
        && item.referencePixelSource[1] > referenceRect[1] && item.referencePixelSource[1] < referenceRect[1] + referenceRect[3]
        && !measurement.cornersSourcePixels.some(corner => equal(corner, item.pixelSource)), `${label}: warp corner fits cannot become interior checks`)
      checks.push(item.referencePixelSource)
    }
  }
  assert(checks.length >= 2 && checks.some(a => checks.some(b => Math.hypot(a[0] - b[0], a[1] - b[1]) >= 0.1 * Math.hypot(referenceRect[2], referenceRect[3]))),
    `${label}: warp needs disjoint spread-out interior source checks`)
  // Residuals belong to stage reports, not the historical 38.4px loading gate.
}

function validateLines(lines, frame, view, paths, label) {
  assert(Array.isArray(lines), `${label}: line observation census is invalid`)
  const ids = new Set(), rect = view.rectSourcePixels
  const inside = point => vector(point, 2) && point[0] >= rect[0] && point[0] < rect[0] + rect[2]
    && point[1] >= rect[1] && point[1] < rect[1] + rect[3]
  for (const line of lines) {
    const evidence = line.measurementEvidence, source = line.sourceLinePixels, local = line.partLocalLineMetres
    assert(text(line.id) && !ids.has(line.id) && paths.has(line.partPath)
      && Array.isArray(local) && local.length === 2 && local.every(point => vector(point, 3))
      && Math.hypot(...local[0].map((value, i) => value - local[1][i])) > 1e-9
      && Array.isArray(source) && source.length === 2 && source.every(inside)
      && Math.hypot(source[0][0] - source[1][0], source[0][1] - source[1][1]) > 1e-6
      && finite(line.uncertaintyPx) && line.uncertaintyPx >= 0
      && equal(evidence?.sourceImage, frame.sourceImage) && text(evidence.detector) && text(evidence.axisPerspectiveEvidence)
      && Array.isArray(evidence.edgeRows) && evidence.edgeRows.length >= 2
      && new Set(evidence.edgeRows.map(row => row.y)).size >= 2, `${label}: line lacks independently measured native/source geometry`)
    ids.add(line.id)
    const delta = source[1].map((value, i) => value - source[0][i]), squared = delta[0] ** 2 + delta[1] ** 2
    for (const row of evidence.edgeRows) {
      assert(inside([row.left, row.y]) && inside([row.right, row.y]) && row.left < row.right
        && finite(row.contrast) && row.contrast > 0, `${label}: line has an invalid observed paired-edge row`)
      const point = [(row.left + row.right) / 2, row.y]
      const fraction = Math.max(0, Math.min(1, point.reduce((sum, value, i) => sum + (value - source[0][i]) * delta[i], 0) / squared))
      assert(Math.hypot(...point.map((value, i) => value - source[0][i] - fraction * delta[i])) <= line.uncertaintyPx,
        `${label}: line is unsupported by its actual paired source edges`)
    }
    assert(Math.min(...source.map(point => point[1])) >= Math.min(...evidence.edgeRows.map(row => row.y)) - line.uncertaintyPx
      && Math.max(...source.map(point => point[1])) <= Math.max(...evidence.edgeRows.map(row => row.y)) + line.uncertaintyPx,
    `${label}: line extends outside actual measured support`)
    nativeLineAxisGeometryBound({ ...view, imagePlaneWarp: view.imagePlaneWarpMeasurement,
      resolvedImagePlaneWarp: view.imagePlaneWarp ?? null }, line,
    [...source, ...evidence.edgeRows.map(row => [(row.left + row.right) / 2, row.y])])
  }
}

export function currentSourceLayoutForViews(views) {
  return views.map(view => ({ viewId: view.id, rectSourcePixels: view.rectSourcePixels,
    presentation: view.presentation, composite: view.composite ?? { mode: 'opaque' },
    resolvedImagePlaneWarp: view.imagePlaneWarp ?? null }))
}

function compileCurrentSourceAssembly(compile, data, frame, view) {
  const label = `${data.source.videoId}@${frame.timeSeconds}/${view.id}`
  try {
    const compiled = compile(view.sourceAssembly)
    assert(compiled.state.kind === 'operating' || compiled.state.provenance.videoId === data.source.videoId,
      'Assembly support witness differs from the current source video')
    return compiled
  } catch (error) { throw new Error(`${label}: ${error.message}`, { cause: error }) }
}

async function withCurrentRuntime(webRoot, consume) {
  const { createServer, createLogger } = await import('vite')
  const logger = createLogger()
  // stdout is the Python bridge's JSON channel; retain SSR diagnostics on stderr.
  logger.info = message => { process.stderr.write(`${message}\n`) }
  const server = await createServer({ root: webRoot, configFile: false, customLogger: logger,
    server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
  try { return await consume(server) }
  finally { await server.close() }
}

/** Runtime capture state comes from the actual compiler, after exact raw-track
 * association. The compiler may normalize accepted unit-vector roundoff in its
 * clone; never rewrite the bound source record or claim this is posed proof. */
export async function normalizeCurrentTrackAssemblies(track, { webRoot = WEB_ROOT } = {}) {
  assert(text(track?.source?.videoId) && Array.isArray(track.frames), 'Current assembly normalization lacks source/frames')
  return withCurrentRuntime(webRoot, async server => {
    const { compileSourceAssemblyState } = await server.ssrLoadModule('/src/source-assembly.ts')
    return { ...track, frames: track.frames.map(frame => {
      assert(Array.isArray(frame.views), 'Current assembly normalization lacks views')
      return { ...frame, views: frame.views.map(view => {
        assert(view && text(view.id) && Object.keys(view).every(key => CURRENT_VIEW_FIELDS.has(key)),
          'Current assembly normalization has an unknown view field/identity')
        return { ...view, sourceAssembly: compileCurrentSourceAssembly(compileSourceAssemblyState, track, frame, view).state }
      }) }
    }) }
  })
}

/** Exact requested-time census of same-shot physical state changes. Source
 * witness/provenance changes are not motion; operating/missing is one baseline.
 * This validates compiled metadata only, never a REST-based posed-state proof. */
export async function currentSourceAssemblyChangeTimes(data, { webRoot = WEB_ROOT } = {}) {
  assert(Array.isArray(data?.frames), 'Current assembly change census lacks frames')
  if (!data.frames.length) return []
  return withCurrentRuntime(webRoot, async server => {
    const { compileSourceAssemblyState, sourceAssemblyPhysicalKey } = await server.ssrLoadModule('/src/source-assembly.ts')
    const operatingKey = sourceAssemblyPhysicalKey(compileSourceAssemblyState(undefined))
    const times = new Set()
    let previous = null, previousTime = -1
    for (const frame of data.frames) {
      assert(finite(frame.timeSeconds) && frame.timeSeconds >= 0 && frame.timeSeconds > previousTime
        && text(frame.shotId) && Array.isArray(frame.views), 'Current assembly change census has an invalid clock/shot/view association')
      previousTime = frame.timeSeconds
      const ids = new Set(), states = []
      for (const view of frame.views) {
        assert(view && text(view.id) && !ids.has(view.id)
          && Object.keys(view).every(key => CURRENT_VIEW_FIELDS.has(key)), 'Current assembly change census has an unknown or duplicate view field/identity')
        ids.add(view.id)
        const key = sourceAssemblyPhysicalKey(compileCurrentSourceAssembly(compileSourceAssemblyState, data, frame, view))
        if (key !== operatingKey) states.push([view.id, key])
      }
      states.sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)
      const key = canonicalJson(states)
      if (previous?.shotId === frame.shotId && previous.key !== key) times.add(frame.timeSeconds)
      previous = { shotId: frame.shotId, key }
    }
    return [...times].sort((a, b) => a - b)
  })
}

/** CPU checks execute the actual input/composite/assembly compilers. They do not
 * claim the REST inventory validates posed constraints: those require the normal
 * solved scene's matrix callbacks and the actual native sampler. */
async function validateCurrentRuntime(data, webRoot) {
  const inputs = data.frames.flatMap(frame => frame.views.filter(view => view.input !== null).map(view => ({ input: view.input, label: `${data.source.videoId}@${frame.timeSeconds}/${view.id}` })))
  if (!data.frames.some(frame => frame.views.length)) return
  return withCurrentRuntime(webRoot, async server => {
    const { compileInput, solveSourceInput } = await server.ssrLoadModule('/src/source-witness.ts')
    const { createMechanismPose } = await server.ssrLoadModule('/src/mechanics.ts')
    const { assertSourceCompositeWeights } = await server.ssrLoadModule('/src/scene.ts')
    const { compileSourceAssemblyState } = await server.ssrLoadModule('/src/source-assembly.ts')
    for (const frame of data.frames) for (const view of frame.views) {
      compileCurrentSourceAssembly(compileSourceAssemblyState, data, frame, view)
    }
    for (const frame of data.frames) assertSourceCompositeWeights(frame.views)
    const pose = createMechanismPose(), solved = new Set()
    for (const { input, label } of inputs) {
      const key = canonicalJson(input)
      if (solved.has(key)) continue
      solveSourceInput(compileInput(input, label), [], pose)
      solved.add(key)
    }
  })
}
function requireCurrentIdentities(data, authority, videoId) {
  assert(data?.schemaVersion === 1 && data.kind === 'current-source-observations', 'Expected independently measured current source observations')
  const source = data.source, expected = authority.videos.get(videoId), model = data.model, identity = data.nativeIdentity
  assert(expected && source?.videoId === videoId && source.sha256 === expected.sha256
    && source.width === 1920 && source.height === 1080 && finite(source.durationSeconds)
    && Math.abs(source.durationSeconds - expected.durationSeconds) <= 0.05
    && Number.isSafeInteger(source.fps?.numerator) && source.fps.numerator > 0
    && Number.isSafeInteger(source.fps.denominator) && source.fps.denominator > 0, 'Current observations differ from the independently known original MP4 identity')
  assert(model?.sha256 === authority.approved.source.sha256 && model.sourceCommit === authority.approved.source.sourceCommit
    && model.units === 'metres' && model.axes === 'X-width/Y-height/Z-depth', 'Current observation model tuple differs from live authority')
  assert(identity && Object.keys(identity).length === 3 && identity.mapSha256 === authority.approved.identity.mapSha256
    && identity.canonicalSha256 === authority.approved.identity.canonicalSha256
    && identity.inventorySha256 === authority.inventorySha256, 'Current observation native map/canonical/inventory association differs')
}


export async function validateCurrentObservations(data, { webRoot = WEB_ROOT, videoId = data?.source?.videoId, inventory = null } = {}) {
  assert(data?.schemaVersion === 1 && data.kind === 'current-source-observations', 'Expected independently measured current source observations')
  rejectLegacy(data)
  const authority = await loadCurrentAuthority(webRoot)
  if (inventory !== null) assert(equal(inventory, authority.inventory), 'Caller inventory differs from the independently sealed actual native export')
  requireCurrentIdentities(data, authority, videoId)
  const source = data.source, model = data.model, identity = data.nativeIdentity
  assert(Array.isArray(data.anchors) && Array.isArray(data.shots) && data.shots.length > 0
    && Array.isArray(data.frames) && data.frames.length > 0, 'Current source census is missing')
  const anchors = validateCurrentAnchors(data, authority)
  const shots = new Map(); let end = 0
  for (const shot of data.shots) {
    assert(text(shot.id) && !shots.has(shot.id) && finite(shot.startSeconds) && Math.abs(shot.startSeconds - end) <= 1e-6
      && finite(shot.endSeconds) && shot.endSeconds > shot.startSeconds && CLASSIFICATIONS.includes(shot.classification)
      && text(shot.reason) && (shot.hasCorrespondingMachine === undefined || typeof shot.hasCorrespondingMachine === 'boolean'), 'Current source shots must form a complete ordered half-open census')
    shots.set(shot.id, shot); end = shot.endSeconds
  }
  assert(Math.abs(end - source.durationSeconds) <= 1e-6, 'Current source shot census does not reach source end')
  const coverage = data.coverage
  assert(['complete', 'blocked'].includes(coverage?.status) && Array.isArray(coverage.blockers)
    && coverage.requiredEveryIntegerSecond === true
    && coverage.blockers.every(row => text(row) || row && text(row.reason)), 'Current source coverage declaration is invalid')
  assert(coverage.status !== 'complete' || coverage.blockers.length === 0, 'Complete current coverage cannot have unresolved blockers')
  const assumptions = nativeGeometryAssumptionErrors(data.nativeGeometryAssumptions)
  assert(!assumptions.length, assumptions.join('; '))
  let previous = -1; const exposures = new Map(), times = new Set(), unresolved = []
  for (const frame of data.frames) {
    const label = `${videoId}@${frame.timeSeconds}`, shot = shots.get(frame.shotId)
    assert(finite(frame.timeSeconds) && frame.timeSeconds > previous && frame.timeSeconds < source.durationSeconds
      && finite(frame.decodedTimeSeconds) && Math.abs(frame.decodedTimeSeconds - frame.timeSeconds) <= 0.5
      && shot && frame.timeSeconds >= shot.startSeconds && frame.timeSeconds < shot.endSeconds
      && frame.decodedTimeSeconds >= shot.startSeconds && frame.decodedTimeSeconds < shot.endSeconds
      && frame.classification === shot.classification, `${label}: current requested/decoded clock or shot classification differs`)
    previous = frame.timeSeconds; times.add(frame.timeSeconds)
    assert(!sourceImageError(frame.sourceImage, source)
      && (frame.decodedFrameIndex === undefined || frame.decodedFrameIndex === frame.sourceImage.frameIndex), `${label}: missing or invalid actual source image identity`)
    assert(Array.isArray(frame.views) && Array.isArray(frame.landmarks), `${label}: current view/landmark census missing`)
    const viewIds = new Set()
    for (const view of frame.views) {
      const viewLabel = `${label}/${view.id}`, rect = view.rectSourcePixels
      assert(view && typeof view === 'object' && !Array.isArray(view)
        && Object.keys(view).every(key => CURRENT_VIEW_FIELDS.has(key)), `${viewLabel}: unknown current view field`)
      assert(text(view.id) && !viewIds.has(view.id) && vector(rect, 4) && rect[0] >= 0 && rect[1] >= 0
        && rect[2] > 0 && rect[3] > 0 && rect[0] + rect[2] <= source.width && rect[1] + rect[3] <= source.height
        && ['native', 'horizontal-mirror'].includes(view.presentation), `${viewLabel}: invalid source layout`)
      viewIds.add(view.id)
      if (view.sourceViewIds !== undefined || view.sourceViewMappingEvidence !== undefined) {
        assert(Array.isArray(view.sourceViewIds) && view.sourceViewIds.length > 0
          && view.sourceViewIds.every(text) && new Set(view.sourceViewIds).size === view.sourceViewIds.length
          && text(view.sourceViewMappingEvidence), `${viewLabel}: source-view mapping lacks explicit unique identities and source evidence`)
      }
      if (view.composite !== undefined) {
        const composite = view.composite
        assert(composite && (composite.mode === 'opaque' && Object.keys(composite).length === 1
          || composite.mode === 'crossfade' && equal(Object.keys(composite).sort(), ['groupId', 'imageLayerId', 'mode', 'opacity'])
          && text(composite.groupId) && text(composite.imageLayerId) && finite(composite.opacity)
          && composite.opacity >= 0 && composite.opacity <= 1), `${viewLabel}: unknown or malformed source composite`)
        assert(composite.mode !== 'crossfade' || text(view.compositeEvidence), `${viewLabel}: source attenuation has no exposure evidence`)
        assert(composite.mode !== 'crossfade' || composite.opacity > 0
          || !(view.nativeLineChecks?.length || frame.landmarks.some(point => (point.viewId ?? 'main') === view.id)),
        `${viewLabel}: source-discernible measurements cannot have zero image contribution`)
      }
      assert(Object.hasOwn(view, 'input') && (view.input === null || completeInput(view.input)), `${viewLabel}: incomplete current physical input`)
      assert(view.provenance?.kind === 'chosen-feasible' && text(view.provenance.evidence)
        && Array.isArray(view.provenance.unobservedInputFields)
        && new Set(view.provenance.unobservedInputFields).size === view.provenance.unobservedInputFields.length
        && view.provenance.unobservedInputFields.every(field => INPUT_FIELDS.includes(field)), `${viewLabel}: missing honest chosen-input provenance`)
      assert(['source-fit', 'source-transfer', 'source-informed-framing'].includes(view.cameraProvenance?.kind)
        && text(view.cameraProvenance.evidence) && text(view.cameraProvenance.family)
        && text(view.cameraContinuityFamily), `${viewLabel}: current camera family evidence is missing`)
      assert(view.cameraInterpolation === undefined || ['held', 'continuous-shot'].includes(view.cameraInterpolation), `${viewLabel}: unknown camera interpolation`)
      assert(view.cameraInterpolation !== 'continuous-shot' || text(view.cameraInterpolationEvidence), `${viewLabel}: camera continuity has no source evidence`)
      assert(Object.hasOwn(view, 'camera'), `${viewLabel}: missing current camera availability`)
      if (view.camera !== null) {
        requireCamera(view.camera, viewLabel)
        const binding = view.cameraMeasurement
        assert(binding && equal(binding.model, model) && equal(binding.nativeIdentity, identity)
          && equal(binding.sourceImage, frame.sourceImage) && text(binding.evidence), `${viewLabel}: camera is not bound to actual current native/source exposure`)
      }
      if (view.input === null || view.camera === null) {
        assert(unavailable(view.unavailable) || unavailable(frame.unavailable), `${viewLabel}: unresolved camera/input cannot be silently available`)
        unresolved.push(`${viewLabel}: current camera/input unresolved`)
      }
      if (view.imagePlaneWarp !== undefined) {
        validateWarp(view.imagePlaneWarpMeasurement, frame, view, data.frames, viewLabel)
      } else assert(view.imagePlaneWarpMeasurement === undefined, `${viewLabel}: warp measurement lacks its compiled current transform`)
      validateLines(view.nativeLineChecks ?? [], frame, view, authority.paths, viewLabel)
    }
    const seen = new Set(), fits = new Set(), checks = new Set()
    for (const point of frame.landmarks) {
      const viewId = point.viewId ?? 'main', key = `${viewId}/${point.anchorId}`
      assert(anchors.has(point.anchorId) && viewIds.has(viewId) && !seen.has(key)
        && ['fit', 'check'].includes(point.role) && point.status === 'observed'
        && ['manual', 'optical-flow', 'image-edge', 'template-match'].includes(point.method)
        && vector(point.pixel, 2) && point.pixel[0] >= 0 && point.pixel[0] < source.width
        && point.pixel[1] >= 0 && point.pixel[1] < source.height && finite(point.uncertaintyPx) && point.uncertaintyPx >= 0,
      `${label}: invalid independent current source landmark`)
      seen.add(key)
      ;(point.role === 'fit' ? fits : checks).add(`${viewId}/${canonicalJson(point.pixel)}`)
    }
    assert(![...fits].some(pixel => checks.has(pixel)), `${label}: source FIT/CHECK pixels must be independently disjoint`)
    if (sourceNeedsMachine(frame, shot) && !frame.views.length) {
      assert(unavailable(frame.unavailable), `${label}: required source layout is unmapped without an explicit reason`)
      unresolved.push(`${label}: required current source layout unresolved`)
    }
    const image = frame.sourceImage, exposureKey = `${image.sourceSha256}/${image.frameIndex}`
    const layout = canonicalJson(currentSourceLayoutForViews(frame.views))
    const assembly = canonicalJson(frame.views.map(view => ({ viewId: view.id, sourceAssembly: view.sourceAssembly })))
    const pixelHash = image.sha256Bgr8 ?? image.sha256Gray8, prior = exposures.get(exposureKey)
    if (prior) {
      assert(prior.pts === frame.decodedTimeSeconds && prior.shotId === frame.shotId && prior.layout === layout
        && prior.assembly === assembly
        && prior.sourceMachineRequirement === frame.sourceMachineRequirement
        && (!prior.hashes.has(image.pixelFormat) || prior.hashes.get(image.pixelFormat) === pixelHash),
        `${label}: identical source exposure has conflicting clock/shot/layout/assembly/pixel associations`)
      prior.hashes.set(image.pixelFormat, pixelHash)
      for (const point of frame.landmarks) {
        const key = `${point.viewId ?? 'main'}/${point.anchorId}`, old = prior.points.get(key)
        assert(!old || equal(old.pixel, point.pixel) && old.role === point.role, `${label}: identical source exposure has conflicting independent measurements`)
        prior.points.set(key, point)
      }
    } else exposures.set(exposureKey, { pts: frame.decodedTimeSeconds, shotId: frame.shotId, layout, assembly,
      sourceMachineRequirement: frame.sourceMachineRequirement, hashes: new Map([[image.pixelFormat, pixelHash]]),
      points: new Map(frame.landmarks.map(point => [`${point.viewId ?? 'main'}/${point.anchorId}`, point])) })
  }
  const requiredTimes = new Set(data.shots.map(shot => shot.startSeconds))
  for (let time = 0; time < source.durationSeconds; time++) requiredTimes.add(time)
  for (const time of coverage.changeTimesSeconds ?? []) {
    assert(finite(time) && time >= 0 && time < source.durationSeconds, 'Current source change census has an invalid time')
    requiredTimes.add(time)
  }
  for (const time of requiredTimes) if (![...times].some(sample => Math.abs(sample - time) <= 1e-6)) unresolved.push(`Current source sample missing at ${time}s`)
  assert(!unresolved.length || coverage.status === 'blocked' && coverage.blockers.length > 0,
    'Current source census claims complete with unresolved time/layout/camera/input coverage')
  await validateCurrentRuntime(data, webRoot)
  return data
}

export async function loadCurrentObservations(webRoot, videoId) {
  assert(VIDEO_IDS.includes(videoId), 'Unknown current source video')
  const data = JSON.parse(await readFile(resolve(webRoot, FRESH_DIRECTORY, `${videoId}.observations.json`), 'utf8'))
  return validateCurrentObservations(data, { webRoot, videoId })
}

/** Readback candidates must be assembled from this exact fresh record, not relabelled old tracks. */
export async function validateCurrentTrackAssociation(track, observations, webRoot = WEB_ROOT) {
  const id = observations.source.videoId, record = track?.sourceRecord
  assert(track?.kind === 'compact-source-track' && track.schemaVersion === 1
    && equal(track.source, observations.source) && equal(track.model, observations.model)
    && equal(track.nativeIdentity, observations.nativeIdentity), 'Compact track differs from current source/native authority')
  assert(record?.kind === 'current-source-observations'
    && record.path === `${FRESH_DIRECTORY}/${id}.observations.json` && hash(record.sha256)
    && text(record.producerPath) && Array.isArray(record.executedInputs) && record.executedInputs.every(text),
  'Compact track lacks its actual fresh observation record and producer execution declaration')
  const raw = await readFile(resolve(webRoot, record.path))
  assert(digest(raw) === record.sha256, 'Compact track fresh observation bytes changed')
  assert(equal(observations, JSON.parse(raw)), 'Readback observation census differs from the exact fresh record bytes')
  rejectLegacy(observations)
  const authority = await loadCurrentAuthority(webRoot)
  requireCurrentIdentities(observations, authority, id)
  validateCurrentAnchors(observations, authority)
  validateCurrentAnchors(track, authority)
  // Direct association callers must also execute the physical domain compiler;
  // an exact source-record hash is not validation of its authored assembly state.
  await currentSourceAssemblyChangeTimes(observations, { webRoot })
  // Reuse the existing publication seal implementation, including its exact
  // mandatory module census and CRLF-to-LF rule; no archive-code fallback.
  const sealCode = `import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("current_source_common",sys.argv[1])
common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
common.WEB=Path(sys.argv[2])
record=json.loads(sys.argv[3])
common.validate_current_generation_seals(record["producerPath"],executed_inputs=record["executedInputs"])
`
  await runTool('python3', ['-c', sealCode, resolve(webRoot, 'scripts/compact-source-common.py'), webRoot, JSON.stringify(record)])
  assert(Array.isArray(track.anchors) && track.anchors.length === observations.anchors.length
    && track.anchors.every((anchor, i) => ['id', 'kind', 'partPath', 'runtimeTemplatePartPath', 'partLocalMetres', 'worldMetres', 'description', 'correspondenceEvidence']
      .every(key => equal(anchor[key], observations.anchors[i][key]))), 'Compact track borrowed or altered current native feature associations')
  assert(Array.isArray(track.shots) && track.shots.length === observations.shots.length
    && track.shots.every((shot, i) => ['id', 'startSeconds', 'endSeconds', 'classification', 'hasCorrespondingMachine', 'reason']
      .every(key => equal(shot[key], observations.shots[i][key]))), 'Compact track altered the independently observed source shot census')
  assert(Array.isArray(track.frames) && track.frames.length > 0, 'Compact current source track has no samples')
  let previous = -1
  for (const frame of track.frames) {
    const shot = observations.shots.find(shot => shot.id === frame.shotId)
    assert(finite(frame.timeSeconds) && frame.timeSeconds > previous && frame.timeSeconds >= 0
      && frame.timeSeconds < observations.source.durationSeconds && finite(frame.decodedTimeSeconds)
      && Math.abs(frame.timeSeconds - frame.decodedTimeSeconds) <= 0.5 && shot
      && frame.timeSeconds >= shot.startSeconds && frame.timeSeconds < shot.endSeconds
      && frame.decodedTimeSeconds >= shot.startSeconds && frame.decodedTimeSeconds < shot.endSeconds
      && frame.classification === shot.classification
      && (frame.sourceMachineRequirement === undefined || frame.sourceMachineRequirement === 'required'),
    `Compact sample ${frame.timeSeconds}s has a stale requested/decoded source clock or classification`)
    previous = frame.timeSeconds
    const candidates = observations.frames.filter(row => equal(row.sourceImage, frame.sourceImage)
      && row.decodedTimeSeconds === frame.decodedTimeSeconds && row.shotId === frame.shotId)
    assert(candidates.length > 0 && candidates.some(row => equal(row.views, frame.views))
      && candidates.every(row => equal(currentSourceLayoutForViews(row.views), currentSourceLayoutForViews(frame.views))
        && row.sourceMachineRequirement === frame.sourceMachineRequirement),
    `Compact sample ${frame.timeSeconds}s borrowed an old camera/input/assembly/layout or source exposure`)
    const landmarkKeys = ['anchorId', 'viewId', 'role', 'pixel', 'status', 'method', 'uncertaintyPx', 'trackingEvidence', 'measurementEvidence']
    assert(Array.isArray(frame.landmarks) && frame.landmarks.every(point => candidates.some(row => row.landmarks.some(original =>
      landmarkKeys.every(key => equal(point[key], original[key]))))),
    `Compact sample ${frame.timeSeconds}s has source pixels not measured in its exact current exposure/layout`)
  }
  return track
}
