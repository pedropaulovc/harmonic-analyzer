import { mkdtemp, open, readFile, rm, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const MODULE_PATH = 'web/src/native-landmark-eligibility.ts'
const BRIDGE_PATH = 'web/scripts/current-native-eligibility-report.mjs'
const CPU_PATH = 'web/scripts/current-first-surface.py'
const PRODUCER_PATHS = [
  'web/src/source-assembly.ts', 'web/src/bindings.ts', 'web/src/mechanics-data.ts',
  'web/src/native-primitive-snapshot.ts', 'web/src/scene.ts', 'web/src/mechanics.ts',
  'web/src/kinematics.ts', 'web/src/magnifier.ts', 'web/src/native-target-shader-feedback.ts',
  'web/model-representation.mjs', CPU_PATH, 'web/content/model-representation.json',
]
const CHUNK_BYTES = 1024 * 1024
const ARRAY_TYPES = { Float32Array, Uint32Array, Float64Array }
const ELIGIBILITY_SCOPE = 'selected-native-stage-pixel-exact-vertex-identity'
const QUALIFICATION = 'selected-pixel-exact-vertex-identity-not-general-landmark-validity-or-source-acceptance'
const digest = bytes => createHash('sha256').update(bytes).digest('hex')

/** Execute the enrolled current typed consumer, without a listening Vite server. */
export async function loadCurrentNativeEligibilityModule(webRoot = WEB_ROOT) {
  const manifest = JSON.parse(await readFile(resolve(webRoot, 'content/canonical-native/manifest.json'), 'utf8'))
  if (manifest.canonicalConsumerHashNormalization !== 'CRLF-to-LF') throw new Error('Current native eligibility consumer hash normalization is unavailable')
  const seals = []
  for (const path of [MODULE_PATH, BRIDGE_PATH, ...PRODUCER_PATHS]) {
    const entries = manifest.canonicalConsumerInputs?.filter(entry => entry.path === path) ?? []
    if (entries.length !== 1 || !/^[a-f0-9]{64}$/.test(entries[0].sha256)) throw new Error(`Current native eligibility consumer seal is unavailable: ${path}`)
    const bytes = await readFile(resolve(webRoot, path.slice('web/'.length)))
    const sha256 = digest(Buffer.from(bytes.toString('utf8').replaceAll('\r\n', '\n')))
    if (sha256 !== entries[0].sha256) throw new Error(`Current native eligibility consumer bytes differ from their seal: ${path}`)
    seals.push({ path, sha256, normalization: 'CRLF-to-LF' })
  }
  const inventorySeal = manifest.currentSourceInventory
  if (inventorySeal?.path !== 'web/content/v39-source/native-inventory.json' || !/^[a-f0-9]{64}$/.test(inventorySeal.sha256)) throw new Error('Current native inventory seal is unavailable')
  const inventoryBytes = await readFile(resolve(webRoot, 'content/v39-source/native-inventory.json'))
  if (digest(inventoryBytes) !== inventorySeal.sha256) throw new Error('Current native inventory bytes differ from their seal')
  const { createServer, createLogger } = await import('vite')
  const logger = createLogger()
  logger.info = message => { process.stderr.write(`${message}\n`) }
  const server = await createServer({ root: webRoot, configFile: false, customLogger: logger,
    server: { middlewareMode: true, hmr: false, ws: false, watch: null }, appType: 'custom' })
  try {
    const module = await server.ssrLoadModule('/src/native-landmark-eligibility.ts')
    const { NATIVE_RUNTIME_INSTANCES } = await server.ssrLoadModule('/src/source-assembly.ts')
    const modelRepresentation = JSON.parse(await readFile(resolve(webRoot, 'content/model-representation.json'), 'utf8'))
    return { ...module, seals, scopeAuthority: { modelRepresentation, runtimeInstances: NATIVE_RUNTIME_INSTANCES,
      sourceConsumerInputs: manifest.canonicalConsumerInputs.filter(entry => PRODUCER_PATHS.includes(entry.path)) } }
  } finally { await server.close() }
}

function cpuBatch(headerPath, queriesPath, webRoot) {
  return new Promise((done, reject) => {
    const child = spawn('python3', [resolve(webRoot, 'scripts/current-first-surface.py'), '--header', headerPath, '--queries', queriesPath],
      { cwd: webRoot, stdio: ['ignore', 'pipe', 'pipe'] })
    const stdout = [], stderr = []
    child.stdout.on('data', chunk => stdout.push(chunk))
    child.stderr.on('data', chunk => stderr.push(chunk))
    child.on('error', reject)
    child.on('close', code => {
      if (code !== 0) { reject(new Error(`Current native CPU first-surface batch failed (${code}): ${Buffer.concat(stderr).toString('utf8')}`)); return }
      try { done(JSON.parse(Buffer.concat(stdout).toString('utf8'))) } catch (error) { reject(error) }
    })
  })
}

/**
 * Full geometry is captured once per explicitly requested current frame, before
 * the diagnostic lease. The lease holds that exact actual draw throughout byte
 * transport, CPU replay and native GPU queries; it never selects an old camera.
 */
export async function collectCurrentNativeEligibilityEvidence(page, frame, response, module, { collect = false, webRoot = WEB_ROOT } = {}) {
  if (!collect) return { snapshot: null, currentMetadata: null, registeredAnchors: [], queries: [],
    collection: { status: 'not-collected', reason: 'opt-in-current-frame-collection-not-requested' } }
  const directory = await mkdtemp(resolve(tmpdir(), 'harmonic-native-eligibility-'))
  let handle
  try {
    handle = await page.evaluateHandle(async viewIds => {
      const api = window.harmonicAnalyzer
      // This is the only normal snapshot call. In-lease snapshots are stale.
      const captures = viewIds.map(viewId => ({ viewId, capture: api.renderedLandmarks(viewId), mechanism: api.renderedMechanism(viewId) }))
      const state = { snapshot: api.nativePrimitiveSnapshot(), captures, currentMetadata: null, registeredAnchors: [], context: null, reason: null, leaseStatus: 'pending' }
      let ready, failed
      const started = new Promise((resolve, reject) => { ready = resolve; failed = reject })
      state.lease = api.withNativeDiagnosticLease(async context => {
        state.context = context
        state.currentMetadata = context.readNativeDrawMetadata()
        state.registeredAnchors = context.readRegisteredNativeLandmarkAnchors()
        state.leaseStatus = 'held'
        await new Promise(resolve => { state.release = resolve; ready() })
      })
      state.lease.catch(failed)
      try { await started } catch (error) { state.leaseStatus = 'refused'; state.leaseError = error; state.reason = error.message }
      return state
    }, frame.views.map(view => view.id))
    const header = await handle.evaluate(state => ({
      snapshot: { ...state.snapshot, buffers: null }, currentMetadata: state.currentMetadata,
      registeredAnchors: state.registeredAnchors, captures: state.captures, reason: state.reason, leaseStatus: state.leaseStatus,
      files: Object.entries(state.snapshot.buffers ?? {}).flatMap(([primitiveId, buffers]) => Object.entries(buffers).map(([name, array]) => ({
        primitiveId, name, arrayType: array.constructor.name, byteLength: array.byteLength,
      }))),
    }))
    const evidence = { snapshot: header.snapshot.status === 'captured' && header.leaseStatus !== 'refused' ? null : header.snapshot, currentMetadata: header.currentMetadata, registeredAnchors: header.registeredAnchors, captures: header.captures,
      queries: [], collection: { status: header.leaseStatus === 'refused' ? 'unavailable' : 'collected', reason: header.reason, snapshotStatus: header.snapshot.status,
        currentNativeDrawOnly: true, bufferCount: header.files.length, byteLength: 0, bufferReceipts: [] } }
    if (header.snapshot.status !== 'captured' || header.leaseStatus === 'refused') return evidence
    const snapshot = { ...header.snapshot, buffers: {} }, files = []
    for (let index = 0; index < header.files.length; index++) {
      const descriptor = header.files[index], Type = ARRAY_TYPES[descriptor.arrayType]
      if (!Type || !Number.isSafeInteger(descriptor.byteLength) || descriptor.byteLength < 0 || descriptor.byteLength % Type.BYTES_PER_ELEMENT) throw new Error('Unsupported native snapshot buffer descriptor')
      const bytes = new Uint8Array(descriptor.byteLength)
      const filename = `buffer-${index}.bin`
      const file = await open(resolve(directory, filename), 'w')
      try {
        for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
          const encoded = await handle.evaluate((state, query) => {
            const array = state.snapshot.buffers[query.primitiveId][query.name]
            const chunk = new Uint8Array(array.buffer, array.byteOffset + query.offset, Math.min(query.length, array.byteLength - query.offset))
            let text = ''
            for (let start = 0; start < chunk.length; start += 8192) text += String.fromCharCode(...chunk.subarray(start, start + 8192))
            return btoa(text)
          }, { ...descriptor, offset, length: CHUNK_BYTES })
          const chunk = Buffer.from(encoded, 'base64')
          if (chunk.length !== Math.min(CHUNK_BYTES, bytes.length - offset)) throw new Error('Incomplete native snapshot byte chunk')
          bytes.set(chunk, offset)
          await file.writeFile(chunk)
        }
      } finally { await file.close() }
      const sha256 = digest(bytes)
      if (!snapshot.buffers[descriptor.primitiveId]) snapshot.buffers[descriptor.primitiveId] = {}
      snapshot.buffers[descriptor.primitiveId][descriptor.name] = new Type(bytes.buffer)
      files.push({ ...descriptor, filename, sha256 })
      evidence.collection.byteLength += bytes.byteLength
      evidence.collection.bufferReceipts.push({ ...descriptor, sha256 })
    }
    evidence.snapshot = snapshot
    const rows = [...snapshot.manifest.primitives, ...snapshot.manifest.runtimeClones]
    for (const observed of frame.landmarks ?? []) {
      const viewId = observed.viewId ?? 'main', queryId = `${viewId}/${observed.anchorId}`
      const anchorRows = evidence.registeredAnchors.filter(anchor => anchor.id === observed.anchorId)
      const anchor = anchorRows.length === 1 ? anchorRows[0] : null
      const query = { queryId, eligibilityScope: ELIGIBILITY_SCOPE, viewId, anchorId: observed.anchorId, anchor, target: null, cpu: null, gpu: null, shaderFeedback: null, mapping: null, reasons: [] }
      evidence.queries.push(query)
      if (evidence.currentMetadata?.status !== 'current-diagnostic-submission' || evidence.currentMetadata.draw.viewId !== viewId) {
        query.reasons.push('Only the last current native draw retains geometry; earlier simultaneous views cannot reuse its camera/context'); continue
      }
      if (!anchor?.partLocalMetres || anchor.worldMetres !== undefined) { query.reasons.push('Exact registered part-local landmark anchor is unavailable'); continue }
      const matches = rows.filter(row => (row.runtimeInstance?.instancePath ?? row.identity.nodePath) === anchor.partPath
        && (row.runtimeInstance?.sourcePartPath ?? null) === (anchor.runtimeTemplatePartPath ?? null))
      const candidates = matches.map(row => ({ row,
        classVertexIds: module.exactStoredF32Class(snapshot.buffers[row.id].localPositions, anchor.partLocalMetres) }))
      const exactCandidates = candidates.filter(candidate => candidate.classVertexIds.length)
      const chosen = candidates.length === 1 ? candidates[0] : exactCandidates.length === 1 ? exactCandidates[0] : null
      if (!chosen) { query.reasons.push('Registered anchor does not select one unique native primitive/class'); continue }
      const { row, classVertexIds } = chosen, buffers = snapshot.buffers[row.id]
      query.classVertexIds = classVertexIds
      query.incidentTriangles = module.incidentOriginalTriangles(buffers.indices, query.classVertexIds, row.vertexCount)
      const marker = evidence.captures.find(entry => entry.viewId === viewId)?.capture?.landmarks.find(marker => marker.id === observed.anchorId)
      if (!marker?.sourcePixels) { query.reasons.push('Actual depth-off GPU source projection is unavailable'); continue }
      query.mapping = await handle.evaluate((state, args) => state.context.resolveNativeStagePixelFromSourcePixel(args.viewId, args.sourcePixels), { viewId, sourcePixels: marker.sourcePixels })
      if (query.mapping.status !== 'mapped') { query.reasons.push(query.mapping.reason); continue }
      query.target = { primitiveId: row.id, exactLocalPosition: anchor.partLocalMetres, nativeStageBackingPixel: query.mapping.nativeStageBackingPixel }
      query.ray = module.deriveNativeStagePixelRay(evidence.currentMetadata.draw, query.target.nativeStageBackingPixel)
      if (query.incidentTriangles.length) {
        const request = { targetPrimitiveId: row.id, exactLocalPosition: anchor.partLocalMetres, targetIndexOffset: query.incidentTriangles[0].indexOffset,
          nativeStageBackingPixel: query.target.nativeStageBackingPixel,
          expectedDrawRevision: evidence.currentMetadata.draw.drawRevision, expectedContextRevision: evidence.currentMetadata.draw.contextRevision,
          expectedViewId: viewId, expectedTimeSeconds: evidence.currentMetadata.draw.timeSeconds }
        query.gpu = await handle.evaluate((state, request) => state.context.readNativeTargetSurfaceAssociation(request), request)
        query.shaderFeedback = await handle.evaluate((state, args) => {
          const manifest = state.snapshot.manifest
          const primitive = [...manifest.primitives, ...manifest.runtimeClones].find(row => row.id === args.request.targetPrimitiveId)
          const world = state.snapshot.buffers[primitive.id].worldPositions
          const worldPositions = new Float64Array(args.classVertexIds.length * 3)
          for (let index = 0; index < args.classVertexIds.length; index++) {
            const start = args.classVertexIds[index] * 3
            worldPositions.set(world.subarray(start, start + 3), index * 3)
          }
          const result = state.context.measureNativeTargetShaderFeedback({ ...args.request, cpuReference: {
            model: manifest.model, machineRevision: manifest.machineRevision, inventoryRevision: manifest.inventoryRevision,
            input: manifest.input, sourceAssembly: manifest.draw.sourceAssembly, matrixWorld: primitive.matrixWorld,
            targetPrimitiveId: primitive.id, targetVertexIndices: args.classVertexIds, worldPositions,
          } })
          const encode = array => {
            if (!array) return null
            const bytes = new Uint8Array(array.buffer, array.byteOffset, array.byteLength)
            let text = ''
            for (let start = 0; start < bytes.length; start += 8192) text += String.fromCharCode(...bytes.subarray(start, start + 8192))
            return { arrayType: array.constructor.name, byteLength: array.byteLength, base64: btoa(text) }
          }
          const feedback = result.feedback
          // Preserve the producer's exact field names and CPU/GPU provenance.
          // Typed readback vectors travel as bytes, never JSON float reformatting.
          return { ...result, feedback: feedback ? Object.fromEntries(Object.entries(feedback).map(([name, value]) =>
            [name, ArrayBuffer.isView(value) ? encode(value) : value])) : null }
        }, { request, classVertexIds: query.classVertexIds })
      }
    }
    const cpuQueries = evidence.queries.filter(query => query.target && query.ray)
    if (cpuQueries.length) {
      const headerPath = resolve(directory, 'manifest.json'), queriesPath = resolve(directory, 'queries.json')
      const headerBytes = Buffer.from(JSON.stringify({ manifest: snapshot.manifest, context: snapshot.context, files, scopeAuthority: module.scopeAuthority }))
      const headerSha256 = digest(headerBytes)
      await writeFile(headerPath, headerBytes)
      await writeFile(queriesPath, JSON.stringify({ headerSha256, metadata: evidence.currentMetadata, queries: cpuQueries.map(query => ({
        queryId: query.queryId, primitiveId: query.target.primitiveId, localCoordinate: query.target.exactLocalPosition,
        origin: query.ray.origin, direction: query.ray.direction, near: query.ray.near, far: query.ray.far,
      })) }))
      try {
        const batch = await cpuBatch(headerPath, queriesPath, webRoot)
        if (batch.schemaVersion !== 1 || batch.method !== 'current-native-cpu-first-surface-batch' || batch.headerSha256 !== headerSha256) throw new Error('Unsupported or differently bound actual CPU first-surface batch result')
        if (batch.eligibilityScope !== 'queried-ray-exact-vertex-identity') throw new Error('Actual CPU first-surface batch has no supported queried-ray eligibility scope')
        for (const query of cpuQueries) {
          const results = batch.results.filter(result => result.queryId === query.queryId)
          if (results.length === 1 && results[0].result) query.cpu = { metadata: batch.metadata, ray: query.ray, bufferReceipts: batch.bufferReceipts, result: results[0].result }
          else query.reasons.push(results[0]?.error ?? 'Actual CPU first-surface result is unavailable or nonunique')
        }
      } catch (error) {
        for (const query of cpuQueries) query.reasons.push(error.message)
      }
    }
    return evidence
  } finally {
    if (handle) {
      try {
        await handle.evaluate(async state => {
          state.release?.()
          try { await state.lease } catch (error) {
            // Only the already-recorded collection refusal is redundant here.
            // New restoration failures still invalidate a successful collection.
            if (state.leaseStatus !== 'refused' || error !== state.leaseError) throw error
          }
        })
      }
      finally { await handle.dispose(); await rm(directory, { recursive: true, force: true }) }
    } else await rm(directory, { recursive: true, force: true })
  }
}

/** Report only: no eligibility field feeds pixel/clock/coverage/playback gates. */
export async function joinCurrentNativeEligibilityReport(joinNativeLandmarkEligibility, frame, response) {
  const evidence = response?.nativeEligibilityEvidence ?? null, landmarks = []
  for (const observed of frame?.landmarks ?? []) {
    const viewId = observed.viewId ?? 'main', entry = evidence?.captures?.find(capture => capture.viewId === viewId)
      ?? response?.captures?.find(capture => capture.viewId === viewId)
    const anchors = evidence?.registeredAnchors?.filter(anchor => anchor.id === observed.anchorId) ?? []
    const anchor = anchors.length === 1 ? anchors[0] : null
    const query = evidence?.queries?.find(query => query.queryId === `${viewId}/${observed.anchorId}`)
    /** @type {import('../src/native-landmark-eligibility.ts').NativeLandmarkEligibilityInput} */
    const input = { snapshot: evidence?.snapshot ?? null, currentMetadata: evidence?.currentMetadata ?? null, target: query?.target ?? null,
      projection: anchor && entry?.capture ? { metadata: evidence?.currentMetadata ?? null, capture: entry.capture, anchor } : null,
      cpu: query?.cpu ?? null, gpu: query?.gpu ?? null, independentGpuProof: query?.independentGpuProof ?? null }
    const result = await joinNativeLandmarkEligibility(input)
    landmarks.push({ viewId, anchorId: observed.anchorId, role: observed.role, ...result,
      collection: evidence?.collection ?? { status: 'not-collected', reason: 'native-evidence-producer-unavailable' },
      registeredAnchor: anchor, projection: entry?.capture ?? null, stagePointMapping: query?.mapping ?? null,
      stagePointMeaning: 'Selected pixel-centre query from executed image support, not general native-anchor visibility/validity or an independently measured native GPU centroid',
      shaderFeedback: query?.shaderFeedback ?? null, collectionReasons: query?.reasons ?? [],
    })
  }
  return { method: 'optional-current-native-landmark-eligibility-report', eligibilityScope: ELIGIBILITY_SCOPE, qualification: QUALIFICATION, gating: false,
    state: landmarks.length && landmarks.every(item => item.state === 'eligible') ? 'eligible'
      : landmarks.some(item => item.state === 'ineligible') ? 'ineligible' : 'unresolved',
    sourceProof: false, sourceAcceptance: false, currentMetadata: evidence?.currentMetadata ?? null, landmarks,
    reasons: landmarks.length ? [...new Set(landmarks.flatMap(item => item.reasons))] : ['No required-frame landmark declarations are available'] }
}

/** A loader/capture refusal stays visible without becoming pixel unavailability. */
export function unavailableCurrentNativeEligibilityReport(frame, reason, collectionReason = 'module-seal-unavailable') {
  return { method: 'optional-current-native-landmark-eligibility-report', eligibilityScope: ELIGIBILITY_SCOPE, qualification: QUALIFICATION, gating: false,
    state: 'unresolved', sourceProof: false, sourceAcceptance: false,
    landmarks: (frame?.landmarks ?? []).map(observed => ({ viewId: observed.viewId ?? 'main', anchorId: observed.anchorId,
      role: observed.role, eligibilityScope: ELIGIBILITY_SCOPE, qualification: QUALIFICATION, state: 'unresolved', reasons: [reason], collection: { status: 'not-collected', reason: collectionReason } })),
    reasons: [reason] }
}
