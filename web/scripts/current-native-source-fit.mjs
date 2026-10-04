#!/usr/bin/env node
/**
 * Private CURRENT462 world export, not source/native/GPU acceptance.
 *
 * Node exports binary64 points from protected raw topology and the independently
 * pinned original CPU pose. Python current-native-source-fit.py consumes this
 * packet with fit-source.py::fit_camera; no full-video census is manufactured.
 *
 * CLI (all executions belong to the root):
 * node web/scripts/current-native-source-fit.mjs --closure ARCHIVE
 *   --closure-sha256 PIN --original-observations ORIGINAL --original-observations-sha256 PIN
 *   --authored-frame PRIVATE_FRAME --authored-frame-sha256 PIN
 *   --selection PRIVATE_SELECTION --selection-sha256 PIN
 *   --decoded-frame PRIVATE_DECODE_PROOF --decoded-frame-sha256 PIN
 *   [--intro-inspection PRIVATE_INSPECTION --intro-inspection-sha256 PIN]
 *   [--spring-oracle SEALED_MODULE --spring-oracle-sha256 PIN]
 *   --output web/.vite/verification-output/NEW_PACKET.json
 *
 * Selection: {viewId, inputSelection:{field:'input'|'chosenInput'|
 * 'mechanicalState.input'|'mechanicalState.chosenInput',
 * state:'chosen-unmeasured'|'independently-measured', evidence, ambiguities:[]},
 * features:[{originalLandmark, sourceBinding, correspondence:{state,evidence},
 * witness}], exactAssociatedAnchors?:[{anchorId,primitiveIndex?}],
 * axisControls?:[...current-native-axis-fit.mjs declarations...],
 * rockerCapAnchors?:[...current-native-rocker-cap-fit.mjs declarations...],
 * cameraFit?:{...existing fit_camera options...}}.
 * sourceBinding is the exact sourceTuple below. witness.sourceFeatureEvidenceSHA256
 * must hash {sourceBinding,originalLandmark,correspondence}. No local coordinate,
 * projected point, old-name fallback or machine-input optimizer is accepted.
 * For Intro809 --intro-inspection constructs only the genuine four head choices;
 * its four FITs remain insufficient. Missing observations remain in rows/original.
 * Output must be new and private; this command cannot publish canonical tracks.
 */
import { realpathSync } from 'node:fs'
import { readFile, writeFile } from 'node:fs/promises'
import { resolve, relative, dirname, sep } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { parseArgs } from 'node:util'
import { CURRENT_NATIVE_RAW_SHA256, CURRENT_NATIVE_DELIVERY_SHA256, canonicalJson, jsonDigest, sha256,
  parseNativeRawGLB, bindNativeRawPrimitivesToOriginalInventory, requireSHA } from './native-model-byte-proof.mjs'
import { readOriginalNativeCPUClosure, createOriginalNativePoseOracle } from './native-original-cpu.mjs'
import { verifyNativeMeshFeatureWitness, transformWitnessPoint, freezeIntroSilverHeadWitnesses } from './native-mesh-feature-witness.mjs'
import { nativeWitnessAtOriginalPoint } from './native-source-feature-bindings.mjs'
import { createCurrentNativeAxisFitDefinitions } from './current-native-axis-fit.mjs'
import { reproveCurrentNativeFitAssociationPrimitives } from './current-native-fit-association.mjs'
import { createCurrentNativeRockerCapFitDefinitions } from './current-native-rocker-cap-fit.mjs'

export const ORIGINAL_SPRING_ORACLE_SHA256 = 'e84fd4318890130e8183ebdcce1560796b24b6e0b4ac3e15b890545c8dd9a5fa'
const clone = value => JSON.parse(canonicalJson(value))
const same = (a, b) => canonicalJson(a) === canonicalJson(b)
const fail = message => { throw new Error(`Current native source fit: ${message}`) }
const finite = (v, n) => Array.isArray(v) && v.length === n && v.every(Number.isFinite)
const text = v => typeof v === 'string' && v.trim().length > 0
const states = ['chosen-unmeasured', 'independently-measured']
const setupKeys = ['meanLineAngleRad', 'platenOffsetM', 'wireFixtureOffsetM', 'coneSwingRad', 'pinionCamRad', 'heldChannelTurns', 'driveCrankOffsetTurns']
const provedWorldTopologies = new WeakMap()

function uniqueById(rows, label) {
  const result = new Map()
  for (const row of rows) {
    if (!text(row?.id) || result.has(row.id)) fail(`${label} has an absent or duplicate anchor identity`)
    result.set(row.id, row)
  }
  return result
}

function validateInput(input) {
  if (!input || !Number.isFinite(input.crankTurns) || !finite(input.amplitudes, 20) || input.amplitudes.some(a => Math.abs(a) > 1)
      || !finite(input.phases, 20) || !['small-large', 'medium-medium', 'large-small'].includes(input.gearing)
      || !(Number.isFinite(input.magnification) && input.magnification > 0) || !input.setup
      || setupKeys.some(k => !Number.isFinite(input.setup[k])) || !Object.hasOwn(input.setup, 'counterHeightM')
      || !(input.setup.counterHeightM === null || Number.isFinite(input.setup.counterHeightM))) fail('complete explicit 51-field authored input required; no defaults or pixel-based input inference')
}

function selectedView(frame, viewId) {
  const matches = (frame.views ?? []).filter(v => v.id === viewId)
  if (frame.views?.length) {
    if (matches.length !== 1) fail('exact authored source view required')
    return matches[0]
  }
  if (viewId !== 'main') fail('unpartitioned source frame has only main view')
  return frame
}

/** Exact exposure binding; ticks are supplied by retained independent decode
 * evidence, never computed from CFR, requested seconds, or candidate pixels. */
export function currentNativeFitSourceTuple(observations, frame, originalViewId, decodedFrame) {
  const source = observations.source, image = frame.sourceImage
  requireSHA(source?.sha256, 'original source video')
  const hashName = { bgr8: 'sha256Bgr8', gray8: 'sha256Gray8' }[image?.pixelFormat]
  if (!hashName || ['sha256Bgr8', 'sha256Gray8'].some(k => k !== hashName && Object.hasOwn(image, k))) fail('exact unconverted original BGR8/gray8 image identity required')
  requireSHA(image[hashName], 'original source image')
  if (!Number.isSafeInteger(image.frameIndex) || image.frameIndex < 0 || image.sourceSha256 !== source.sha256
      || image.width !== source.width || image.height !== source.height) fail('exact original source image identity required')
  if (!Number.isFinite(frame.timeSeconds) || !Number.isFinite(frame.decodedTimeSeconds)) fail('finite numeric original source clocks required')
  if (!decodedFrame || decodedFrame.frameIndex !== image.frameIndex || decodedFrame.sourceSha256 !== source.sha256
      || decodedFrame[hashName] !== image[hashName] || !Number.isSafeInteger(decodedFrame.decodedTimestampTicks)
      || !/^\d+\/\d+$/.test(decodedFrame.timeBase ?? '') || !Number.isFinite(decodedFrame.decodedTimeSeconds)) fail('independently retained exact decoded frame/PTS/image correspondence required')
  const [numerator, denominator] = decodedFrame.timeBase.split('/').map(Number)
  if (!(Number.isSafeInteger(numerator) && numerator > 0 && Number.isSafeInteger(denominator) && denominator > 0)
      || Math.abs(decodedFrame.decodedTimestampTicks * numerator / denominator - decodedFrame.decodedTimeSeconds) > 1e-9
      || Math.abs(frame.decodedTimeSeconds - decodedFrame.decodedTimeSeconds) > 0.5
      || Math.abs(frame.timeSeconds - decodedFrame.decodedTimeSeconds) > 0.5) fail('independent PTS/time-base or original source clock mismatch')
  return { videoId: source.videoId, sourceSha256: source.sha256, sourceImage: clone(image),
    timeSeconds: frame.timeSeconds, decodedTimeSeconds: decodedFrame.decodedTimeSeconds,
    recordedOriginalDecodedTimeSeconds: frame.decodedTimeSeconds, shotId: frame.shotId,
    frameIndex: image.frameIndex, decodedTimestampTicks: decodedFrame.decodedTimestampTicks,
    timeBase: decodedFrame.timeBase, originalViewId }
}

/** Bind an exact authored frame without substituting its historical camera,
 * native anchor, or source input-status claims for current truth. */
export function prepareCurrentNativeFitSource({ originalObservations, authoredFrame, viewId, decodedFrame, inputSelection }) {
  if (!originalObservations?.source || !Array.isArray(originalObservations.frames) || !authoredFrame?.sourceImage) fail('original observations and exact authored frame required')
  const candidates = originalObservations.frames.filter(f => f.sourceImage?.frameIndex === authoredFrame.sourceImage.frameIndex
    && f.timeSeconds === authoredFrame.timeSeconds && f.shotId === authoredFrame.shotId)
  if (candidates.length !== 1) fail('authored exposure does not identify exactly one original source frame')
  const originalFrame = candidates[0], authoredView = selectedView(authoredFrame, viewId)
  if (!same(originalFrame.sourceImage, authoredFrame.sourceImage) || originalFrame.decodedTimeSeconds !== authoredFrame.decodedTimeSeconds) fail('authored source image/decoded time changed from original')
  const originalViewId = authoredView.originalViewId ?? viewId
  const originalView = selectedView(originalFrame, originalViewId)
  const rect = originalFrame.views?.length ? originalView.rectSourcePixels : [0, 0, originalObservations.source.width, originalObservations.source.height]
  if (!finite(rect, 4) || rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0
      || rect[0] + rect[2] > originalObservations.source.width || rect[1] + rect[3] > originalObservations.source.height) fail('original source viewport is invalid')
  if (authoredFrame.views?.length && !same(authoredView.rectSourcePixels, rect)) fail('authored viewport changed original source layout')
  const presentation = originalView.presentation ?? originalFrame.presentation ?? 'native'
  if (!['native', 'horizontal-mirror'].includes(presentation)
      || (authoredView.presentation ?? authoredFrame.presentation ?? 'native') !== presentation) fail('original source presentation must remain unchanged')
  const sourceBinding = currentNativeFitSourceTuple(originalObservations, originalFrame, originalViewId, decodedFrame)
  if (!inputSelection || !['input', 'chosenInput', 'mechanicalState.input', 'mechanicalState.chosenInput'].includes(inputSelection.field) || !states.includes(inputSelection.state)
      || !text(inputSelection.evidence) || !Array.isArray(inputSelection.ambiguities)
      || inputSelection.ambiguities.some(a => !text(a))) fail('explicit input selection state, evidence and ambiguity ledger required')
  if ((inputSelection.field.endsWith('chosenInput') || authoredView.provenance?.kind === 'chosen-feasible'
      || authoredView.provenance?.unobservedInputFields?.length) && inputSelection.state !== 'chosen-unmeasured') fail('chosenInput/authored unobserved input cannot be promoted to independent source truth')
  const input = inputSelection.field.startsWith('mechanicalState.')
    ? authoredView.mechanicalState?.[inputSelection.field.slice('mechanicalState.'.length)] : authoredView[inputSelection.field]
  validateInput(input)
  // Absent optional source-track overrides author no whole-part operation.
  const partOverrides = authoredView.partOverrides ?? authoredFrame.partOverrides ?? []
  if (!Array.isArray(partOverrides)) fail('exact authored partOverrides must be an array')
  const landmarks = (originalFrame.landmarks ?? []).filter(l => (l.viewId ?? 'main') === originalViewId)
  const seen = new Set()
  for (const l of landmarks) {
    if (!text(l.anchorId) || seen.has(l.anchorId)) fail('original view has ambiguous duplicate anchor identity')
    seen.add(l.anchorId)
    if (l.status === 'observed' && (!['fit', 'check'].includes(l.role) || !finite(l.pixel, 2)
        || l.pixel[0] < rect[0] || l.pixel[1] < rect[1] || l.pixel[0] >= rect[0] + rect[2] || l.pixel[1] >= rect[1] + rect[3])) fail('original observed role/pixel is invalid')
    const authored = (authoredFrame.landmarks ?? []).filter(a => a.anchorId === l.anchorId && (a.originalViewId ?? a.viewId ?? 'main') === originalViewId)
    if (l.status === 'observed' && (authored.length !== 1 || !same(l.pixel, authored[0].pixel) || authored[0].role !== l.role
        || !same(l.uncertaintyPx ?? null, authored[0].uncertaintyPx ?? null))) fail(`${l.anchorId}: authored original role/pixel/uncertainty changed or omitted`)
  }
  return { originalFrame, originalView, authoredView, sourceBinding, landmarks, input, partOverrides,
    viewport: { rectSourcePixels: clone(rect), width: rect[2], height: rect[3], presentation },
    imagePlaneWarp: originalView.imagePlaneWarp ?? originalFrame.imagePlaneWarp ?? authoredView.imagePlaneWarp ?? authoredFrame.imagePlaneWarp
      ?? originalView.resolvedImagePlaneWarp ?? originalFrame.resolvedImagePlaneWarp
      ?? authoredView.resolvedImagePlaneWarp ?? authoredFrame.resolvedImagePlaneWarp ?? null }
}

/** Original slotted-head source facts produce four chosen-unmeasured raw
 * triangle witnesses only. Cap/rim vertices are not extra source FIT/CHECKs. */
export function createIntroCurrentNativeFitDefinitions({ nativeModel, sourceInspection, source }) {
  return freezeIntroSilverHeadWitnesses(nativeModel, sourceInspection).map(head => {
    const originalLandmark = source.landmarks.find(l => l.anchorId === head.witness.anchorId)
    if (!originalLandmark || originalLandmark.role !== 'fit' || !same(originalLandmark.pixel, head.sourceBinding.pixel)
        || originalLandmark.uncertaintyPx !== head.sourceBinding.uncertaintyPx) fail('Intro original four FIT pixel/uncertainty identities required')
    const correspondence = { state: 'chosen-unmeasured', evidence: clone(head.correspondenceChoice) }
    const evidence = { sourceBinding: source.sourceBinding, originalLandmark: clone(originalLandmark), correspondence }
    return { ...evidence, witness: { ...clone(head.witness), sourceFeatureEvidenceSHA256: jsonDigest(evidence) } }
  })
}

/** Explicitly selected existing associations are re-proved against actual raw
 * attribute/index/material bytes and original CPU rest ancestry. This is not a
 * name-based mapping: unsupported/ambiguous coordinates stay unavailable. A
 * virtual axis in a cavity needs its own genuine section/axis definition.
 * Historical world coordinates and historical cameras are never read here. */
export function createExactAssociatedCurrentNativeFitDefinitions({ nativeModel, poseOracle, originalObservations, currentAnchors, source, selections }) {
  if (!Array.isArray(selections) || !Array.isArray(currentAnchors)) fail('explicit exact-association selections/current anchors required')
  const originals = uniqueById(originalObservations.anchors ?? [], 'Original source anchors')
  const anchors = uniqueById(currentAnchors, 'Current source anchors'), inventory = new Map(poseOracle.inventory.drawables.map(d => [d.path, d]))
  const selected = new Set()
  return selections.map(selection => {
    const id = selection?.anchorId, originalLandmark = source.landmarks.find(l => l.anchorId === id), anchor = anchors.get(id)
    if (!originalLandmark || selected.has(id)) fail('unknown/duplicate exact-association source control')
    selected.add(id)
    const correspondence = { state: 'chosen-unmeasured', evidence: { kind: 'reproved-exact-original-native-local-feature',
      currentAnchor: clone(anchor ?? null), qualification: 'Exact local surface construction only; source depth, lens, pose choice and first-surface/GPU acceptance remain unmeasured.' } }
    const evidence = { sourceBinding: source.sourceBinding, originalLandmark: clone(originalLandmark), correspondence }
    try {
      const candidates = []
      for (const primitive of reproveCurrentNativeFitAssociationPrimitives({ nativeModel, inventoryByPath: inventory,
        originalAnchor: originals.get(id), anchor, primitiveIndex: selection.primitiveIndex })) {
        try { candidates.push(nativeWitnessAtOriginalPoint(primitive, anchor.partLocalMetres, id, jsonDigest(evidence))) }
        catch { /* A cavity/virtual coordinate is not a surface control. */ }
      }
      if (candidates.length !== 1) fail(candidates.length ? 'exact associated point has ambiguous raw primitive support; select an explicit primitiveIndex'
        : 'exact association has no closed raw surface witness; genuine axis/section construction or missing current primitive evidence remains required')
      return { ...evidence, witness: candidates[0] }
    } catch (error) { return { ...evidence, witness: null, unavailableReason: error.message } }
  })
}

function originalSpringPoint(original, primitive, pose, witness, springFactory, mechanismData) {
  if (!springFactory) fail('protected independently pinned original spring oracle required')
  if (!['mesh-vertex', 'native-nib-apex', 'triangle-point'].includes(witness.kind)) fail('spring feature must identify stored vertex or genuine triangle point; constructed axes/sections are unsupported')
  const spring = springFactory(mechanismData, original.spring.stock, original.spring.restLengthM)
  const indices = witness.kind === 'triangle-point' ? Array.from(primitive.index.subarray(witness.triangleIndex * 3, witness.triangleIndex * 3 + 3))
    : [witness.kind === 'native-nib-apex' ? witness.apexVertexIndices[0] : witness.vertexIndex]
  const attributes = original.attributes, classified = { kind: 0, t: 0, centre: new Float64Array(3), tangent: new Float64Array(3) }
  const deformed = []
  for (const index of indices) {
    const p = index * 3, raw = primitive.positions.subarray(p, p + 3)
    if (!attributes?.position || [0, 1, 2].some(j => attributes.position.array[p + j] !== raw[j])) fail('original spring vertex identity differs from protected raw POSITION')
    spring.classify(raw[0], raw[1], raw[2], classified)
    const expected = { springCoordinate: [classified.kind, classified.t], springRestCentre: [...classified.centre], springRestTangent: [...classified.tangent] }
    for (const [name, values] of Object.entries(expected)) {
      const attribute = attributes[name]
      if (!attribute || attribute.itemSize !== values.length || values.some((v, j) => attribute.array[index * values.length + j] !== Math.fround(v))) fail('spring attributes disagree with original CPU classification')
    }
    const out = new Float64Array(3)
    spring.deform(attributes, pose.springLengthM, index, out)
    deformed.push(out)
  }
  if (deformed.length === 1) return Array.from(deformed[0])
  const w = witness.barycentric, [a, b, c] = deformed
  return [0, 1, 2].map(j => a[j] + w[1] * (b[j] - a[j]) + w[2] * (c[j] - a[j]))
}

/** Arithmetic boundary exposed for deterministic geometry/duplicate/refusal
 * tests. Its arguments must be the independently parsed raw primitive and
 * original CPU inventory/pose, not browser receipts or submitted matrices. */
export function currentNativeFitWorldPoint({ primitive, original, pose, witness, springFactory, mechanismData }) {
  if (!primitive || !original || !pose || ![true, 'visible'].includes(pose.effectiveVisibility)) fail('exact raw primitive/original pose is missing or hidden')
  const a = original.association
  if (!a || a.nodeIndex !== primitive.nodeIndex || a.primitiveIndex !== primitive.primitiveIndex
      || !Number.isSafeInteger(a.meshIndex) || a.meshIndex < 0
      || (original.instanceOf ?? null) !== (primitive.instanceOf ?? null) || original.path !== primitive.path || pose.path !== original.path) fail('original/raw feature ancestry differs; no name or nearest-vertex mapping')
  // Original GLTFLoader associations name DELIVERY mesh ordinals; raw source
  // mesh ordinals differ after delivery deduplication. The established raw join
  // binds exact node/primitive ancestry, not equality of these two mesh indices.
  // Independently verify full decoded position/index topology before using the
  // original delivery drawable's pose for its protected raw feature.
  let proved = provedWorldTopologies.get(primitive)
  if (!proved?.has(original)) {
    const positions = original.attributes?.position?.array, indices = original.canonicalIndices
    if (!positions || !indices || positions.length !== primitive.positions.length || indices.length !== primitive.index.length) fail('original delivery drawable lacks exact protected raw topology')
    for (let i = 0; i < positions.length; i++) if (positions[i] !== primitive.positions[i]) fail('original delivery POSITION differs from protected raw geometry')
    for (let i = 0; i < indices.length; i++) if (indices[i] !== primitive.index[i]) fail('original delivery indices differ from protected raw topology')
    if (!proved) { proved = new WeakSet(); provedWorldTopologies.set(primitive, proved) }
    proved.add(original)
  }
  const feature = verifyNativeMeshFeatureWitness(witness, primitive)
  const local = original.spring ? originalSpringPoint(original, primitive, pose, witness, springFactory, mechanismData) : feature.localPointMetres
  const world = transformWitnessPoint(pose.matrixWorld, local)
  if (!world.every(Number.isFinite)) fail('original binary64 world point is nonfinite')
  return { worldMetres: world, localMetres: clone(local), rawLocalMetres: clone(feature.localPointMetres),
    supportTriangleIndices: [...feature.supportTriangleIndices], pointIsSurfacePoint: feature.pointIsSurfacePoint,
    deformation: original.spring ? 'protected-original-binary64-spring' : 'original-binary64-rigid-pose',
    springLengthM: original.spring ? pose.springLengthM : null }
}

/** Coincident seams/apex indices cannot raise support counts. In particular a
 * CHECK at a FIT's physical point is not independent, even with another id. */
export function independentCurrentNativeFitRows(rows) {
  const byPoint = new Map()
  for (const row of rows) if (row.status === 'world-exported') {
    const key = canonicalJson(row.worldMetres)
    if (!byPoint.has(key)) byPoint.set(key, [])
    byPoint.get(key).push(row)
  }
  for (const group of byPoint.values()) {
    const representative = group.find(r => r.originalLandmark.role === 'fit') ?? group[0]
    for (const row of group) if (row !== representative) {
      row.status = 'unmeasured-native'
      row.reason = 'Coincident physical point is one support, not an independent FIT/CHECK control'
      row.duplicateOf = representative.originalLandmark.anchorId
    }
  }
  return rows
}

export function exportCurrentNativeSourceFit({ nativeModel, poseOracle, originalObservations, authoredFrame, viewId,
  decodedFrame, inputSelection, featureDefinitions, springFactory = null, provenance, cameraFit = {}, authoredContext = null }) {
  if (nativeModel?.rawSHA256 !== CURRENT_NATIVE_RAW_SHA256 || !(nativeModel.primitives instanceof Map)
      || poseOracle?.inventory?.rawSHA256 !== CURRENT_NATIVE_RAW_SHA256 || poseOracle.inventory.deliverySHA256 !== CURRENT_NATIVE_DELIVERY_SHA256
      || !poseOracle.solve) fail('independently protected current raw and pinned original CPU pose authority required')
  requireSHA(poseOracle.inventory.closureSHA256, 'original CPU closure manifest')
  for (const key of ['originalObservationsSHA256', 'authoredFrameSHA256', 'selectionSHA256', 'decodedFrameSHA256']) requireSHA(provenance?.[key], key)
  if (springFactory && provenance.springOracleSHA256 !== ORIGINAL_SPRING_ORACLE_SHA256) fail('foreign/unpinned spring oracle')
  const source = prepareCurrentNativeFitSource({ originalObservations, authoredFrame, viewId, decodedFrame, inputSelection })
  if (!Array.isArray(featureDefinitions)) fail('explicit current raw feature definitions array required')
  const definitions = new Map()
  for (const definition of featureDefinitions) {
    const id = definition?.originalLandmark?.anchorId
    if (!id || definitions.has(id) || !source.landmarks.some(l => l.anchorId === id)) fail('unknown/duplicate selected source feature identity')
    definitions.set(id, definition)
  }
  const originals = new Map(poseOracle.inventory.drawables.map(d => [d.path, d]))
  const posed = poseOracle.solve(source.input, source.partOverrides)
  const poses = new Map(posed.drawables.map(d => [d.path, d]))
  const anchors = uniqueById(originalObservations.anchors ?? [], 'Original source anchors')
  const rows = source.landmarks.map(originalLandmark => {
    const row = { originalLandmark: clone(originalLandmark), originalAnchor: clone(anchors.get(originalLandmark.anchorId) ?? null), status: 'unmeasured-native' }
    try {
      const d = definitions.get(originalLandmark.anchorId)
      if (originalLandmark.status !== 'observed' || !['fit', 'check'].includes(originalLandmark.role)) fail('original source point is not an observed FIT/CHECK')
      if (!d) fail('no independently selected current raw primitive/pose/source-feature correspondence')
      row.selectedDefinition = clone(d)
      if (!same(d.originalLandmark, originalLandmark) || !same(d.sourceBinding, source.sourceBinding)) fail('selected original landmark role/pixel/uncertainty/source tuple changed')
      if (d.unavailableReason) fail(d.unavailableReason)
      if (!states.includes(d.correspondence?.state) || !d.correspondence.evidence) fail('current source correspondence choice/evidence missing')
      const evidence = { sourceBinding: d.sourceBinding, originalLandmark: d.originalLandmark, correspondence: d.correspondence }
      if (d.witness?.anchorId !== originalLandmark.anchorId || d.witness.sourceFeatureEvidenceSHA256 !== jsonDigest(evidence)) fail('source feature witness does not seal the exact original observation/choice')
      const primitive = nativeModel.primitives.get(d.witness.partPath), original = originals.get(d.witness.partPath), pose = poses.get(d.witness.partPath)
      Object.assign(row, currentNativeFitWorldPoint({ primitive, original, pose, witness: d.witness, springFactory, mechanismData: poseOracle.inventory.mechanismData }),
        { status: 'world-exported', correspondenceState: d.correspondence.state, matrixWorldF64: Array.from(pose.matrixWorld) })
    } catch (error) { row.reason = error.message }
    return row
  })
  independentCurrentNativeFitRows(rows)
  const available = rows.filter(r => r.status === 'world-exported'), fit = available.filter(r => r.originalLandmark.role === 'fit'), check = available.filter(r => r.originalLandmark.role === 'check')
  const reasons = []
  if (fit.length < 6 || check.length < 2) reasons.push(`Need >=6 distinct original FIT and >=2 held-out CHECK; exported ${fit.length}/${check.length}`)
  if (source.imagePlaneWarp !== null) reasons.push('Image-plane warp is separate: original four corner FITs and disjoint interior CHECK obligations unchanged; camera-only fit refuses warped views')
  const [x, y, width] = source.viewport.rectSourcePixels
  const landmarks = available.map(r => {
    const l = clone(r.originalLandmark)
    l.pixel = [l.pixel[0] - x, l.pixel[1] - y]
    if (source.viewport.presentation === 'horizontal-mirror') l.pixel[0] = width - 1 - l.pixel[0]
    return l
  })
  return { schemaVersion: 1, kind: 'current-native-source-camera-fit-packet', sourceAcceptance: false, nativeAcceptance: false,
    model: { rawSHA256: nativeModel.rawSHA256, deliverySHA256: poseOracle.inventory.deliverySHA256, originalCPUClosureSHA256: poseOracle.inventory.closureSHA256 },
    provenance: clone(provenance), sourceBinding: source.sourceBinding,
    original: { source: clone(originalObservations.source), model: clone(originalObservations.model), frame: clone(source.originalFrame),
      view: source.originalView === source.originalFrame ? null : clone(source.originalView), anchors: clone(originalObservations.anchors ?? []) },
    authored: { frame: clone(authoredFrame), context: clone(authoredContext), input: clone(source.input), partOverrides: clone(source.partOverrides), inputSelection: clone(inputSelection) },
    rows, eligibility: { ready: reasons.length === 0, reasons, distinctFitCount: fit.length, distinctCheckCount: check.length,
      unmeasuredCount: rows.length - available.length },
    cameraInput: { frame: { landmarks }, points: Object.fromEntries(available.map(r => [r.originalLandmark.anchorId, r.worldMetres])),
      viewport: source.viewport, thresholdPx: originalObservations.source.width * 0.02, cameraFit: clone(cameraFit) },
    limitations: ['Candidate only; no source, camera, texture, raster, first-surface, body, continuous-playback or GPU acceptance.',
      'Exact authored inputs/whole-part overrides are held fixed, not recovered or optimized from these pixels.',
      'Chosen-unmeasured inputs and feature correspondences remain choices; historical signs/homes do not transfer.',
      'Square pixels and centered principal point are the default gauge, not recovered lens intrinsics. Coplanar focal/depth branches remain possible.',
      'Only original point FITs choose the camera candidate; original CHECKs remain held out. Unmapped original observations remain explicit in rows/original.'] }
}

async function pinnedJSON(path, pin, label) {
  requireSHA(pin, `${label} independent byte pin`)
  const bytes = await readFile(path)
  if (sha256(bytes) !== pin) fail(`${label} independent byte pin mismatch`)
  return JSON.parse(bytes.toString('utf8'))
}

async function readSpringFactory(path, pin) {
  if (pin !== ORIGINAL_SPRING_ORACLE_SHA256) fail('only the independently sealed original spring oracle pin is permitted')
  const bytes = await readFile(path)
  if (sha256(bytes) !== pin) fail('sealed original spring oracle bytes changed')
  // Import precisely the checked bytes, rather than re-opening a mutable path.
  const module = await import(`data:text/javascript;base64,${bytes.toString('base64')}`)
  if (typeof module.createOriginalSpringOracle !== 'function') fail('sealed original spring oracle export missing')
  return module.createOriginalSpringOracle
}

export function assertPrivateCurrentNativeFitOutput(path) {
  const privateRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../.vite/verification-output'), output = resolve(path)
  const suffix = relative(privateRoot, output)
  if (!suffix || suffix === '..' || suffix.startsWith(`..${sep}`) || suffix.startsWith(sep)) fail('output must be a new private web/.vite/verification-output file, never canonical source content')
  const actualPrivateRoot = realpathSync(privateRoot), actualParent = realpathSync(dirname(output))
  const actualSuffix = relative(actualPrivateRoot, actualParent)
  if (actualSuffix === '..' || actualSuffix.startsWith(`..${sep}`) || actualSuffix.startsWith(sep)) fail('output must be a new private web/.vite/verification-output file, never canonical source content')
  return output
}

async function main() {
  const names = ['closure', 'closure-sha256', 'original-observations', 'original-observations-sha256', 'authored-frame', 'authored-frame-sha256',
    'selection', 'selection-sha256', 'decoded-frame', 'decoded-frame-sha256', 'intro-inspection', 'intro-inspection-sha256', 'spring-oracle', 'spring-oracle-sha256', 'output']
  const { values } = parseArgs({ options: Object.fromEntries(names.map(n => [n, { type: 'string' }])) })
  for (const n of names.slice(0, 10).concat('output')) if (!values[n]) fail(`--${n} required; see module header`)
  const output = assertPrivateCurrentNativeFitOutput(values.output)
  const [originalObservations, authoredDocument, selection, decodedFrame, closure] = await Promise.all([
    pinnedJSON(values['original-observations'], values['original-observations-sha256'], 'original observations'),
    pinnedJSON(values['authored-frame'], values['authored-frame-sha256'], 'exact authored frame'),
    pinnedJSON(values.selection, values['selection-sha256'], 'feature/input selection'),
    pinnedJSON(values['decoded-frame'], values['decoded-frame-sha256'], 'independent decoded frame'),
    readOriginalNativeCPUClosure({ archive: values.closure, manifestSHA256: values['closure-sha256'] }),
  ])
  const authoredFrame = authoredDocument.kind === 'parent-current-authored-source-frame-extraction' ? authoredDocument.frame : authoredDocument
  const poseOracle = await createOriginalNativePoseOracle({ closure })
  try {
    const raw = parseNativeRawGLB(closure.rawGLBBytes)
    // Raw tree names (459) are not loader-generated runtime names (479):
    // raw 460 primitive instances join original 462 leaves including two clones.
    if (sha256(closure.rawGLBBytes) !== CURRENT_NATIVE_RAW_SHA256 || raw.nodes.size !== 459 || raw.primitives.size !== 460) fail('protected raw 460 primitive-instance/459 named-path identity changed')
    const nativeModel = { ...raw, rawSHA256: CURRENT_NATIVE_RAW_SHA256, primitives: bindNativeRawPrimitivesToOriginalInventory(raw, poseOracle.inventory) }
    const provenance = { originalObservationsSHA256: values['original-observations-sha256'], authoredFrameSHA256: values['authored-frame-sha256'],
      selectionSHA256: values['selection-sha256'], decodedFrameSHA256: values['decoded-frame-sha256'] }
    let features = selection.features
    if (values['intro-inspection']) {
      const sourceInspection = await pinnedJSON(values['intro-inspection'], values['intro-inspection-sha256'], 'primary Intro inspection')
      const source = prepareCurrentNativeFitSource({ originalObservations, authoredFrame, viewId: selection.viewId, decodedFrame, inputSelection: selection.inputSelection })
      if (source.sourceBinding.videoId !== 'NAsM30MAHLg' || source.sourceBinding.frameIndex !== 809 || features?.length) fail('Intro mode is only original frame809; cannot override or add head controls implicitly')
      features = createIntroCurrentNativeFitDefinitions({ nativeModel, sourceInspection, source })
      provenance.introInspectionSHA256 = values['intro-inspection-sha256']
    }
    if (selection.exactAssociatedAnchors?.length) {
      const source = prepareCurrentNativeFitSource({ originalObservations, authoredFrame, viewId: selection.viewId, decodedFrame, inputSelection: selection.inputSelection })
      features = [...(features ?? []), ...createExactAssociatedCurrentNativeFitDefinitions({ nativeModel, poseOracle, originalObservations,
        currentAnchors: authoredDocument.anchors, source, selections: selection.exactAssociatedAnchors })]
    }
    if (selection.axisControls?.length) {
      const source = prepareCurrentNativeFitSource({ originalObservations, authoredFrame, viewId: selection.viewId, decodedFrame, inputSelection: selection.inputSelection })
      features = [...(features ?? []), ...createCurrentNativeAxisFitDefinitions({ nativeModel, originalObservations, source, controls: selection.axisControls })]
    }
    if (selection.rockerCapAnchors?.length) {
      const source = prepareCurrentNativeFitSource({ originalObservations, authoredFrame, viewId: selection.viewId, decodedFrame, inputSelection: selection.inputSelection })
      features = [...(features ?? []), ...createCurrentNativeRockerCapFitDefinitions({ nativeModel, poseOracle, originalObservations,
        currentAnchors: authoredDocument.anchors, source, selections: selection.rockerCapAnchors })]
    }
    let springFactory = null
    if (values['spring-oracle']) {
      springFactory = await readSpringFactory(values['spring-oracle'], values['spring-oracle-sha256'])
      provenance.springOracleSHA256 = values['spring-oracle-sha256']
    }
    const packet = exportCurrentNativeSourceFit({ nativeModel, poseOracle, originalObservations, authoredFrame, viewId: selection.viewId,
      decodedFrame, inputSelection: selection.inputSelection, featureDefinitions: features, springFactory, provenance, cameraFit: selection.cameraFit ?? {},
      authoredContext: authoredDocument.kind === 'parent-current-authored-source-frame-extraction'
        ? { sourceTrack: authoredDocument.sourceTrack, originalObservations: authoredDocument.originalObservations,
          source: authoredDocument.source, model: authoredDocument.model, anchors: authoredDocument.anchors } : null })
    await writeFile(output, `${JSON.stringify(packet, null, 2)}\n`, { flag: 'wx' })
    console.log(JSON.stringify({ output, ...packet.eligibility, sourceAcceptance: false, nativeAcceptance: false }))
    if (!packet.eligibility.ready) process.exitCode = 2
  } finally { poseOracle.dispose() }
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) main().catch(error => {
  console.error(error.message)
  process.exitCode = 1
})
