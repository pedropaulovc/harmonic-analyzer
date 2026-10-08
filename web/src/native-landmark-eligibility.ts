import type { LandmarkAnchor, NativeTargetSurfaceReadback, RenderedLandmarks } from './scene'
import type {
  NativePrimitiveBuffers, NativePrimitiveDraw, NativePrimitiveIdentity, NativePrimitiveManifest, NativePrimitiveSnapshot,
  NativePrimitiveSubmissionMetadata,
} from './native-primitive-snapshot'

/** Geometry, GPU arithmetic and source/raster uncertainty remain separate budgets. */
export const NATIVE_LANDMARK_GEOMETRIC_TOLERANCE_METRES = 1e-7
/** Classifies one pixel-centre query, never a native landmark's general visibility or validity. */
export const NATIVE_LANDMARK_ELIGIBILITY_SCOPE = 'selected-native-stage-pixel-exact-vertex-identity' as const
export type NativeLandmarkPoint = readonly [number, number, number]
export type NativeLandmarkPixel = readonly [number, number]
type CapturedSnapshot = Extract<NativePrimitiveSnapshot, { status: 'captured' }>
type CurrentMetadata = Extract<NativePrimitiveSubmissionMetadata, { status: 'current-diagnostic-submission' }>

export interface NativeIncidentTriangle {
  triangleIndex: number
  indexOffset: number
  vertexIds: readonly [number, number, number]
}

/** Exact numeric stored-F32 equality, including signed-zero equality; never cast the query. */
export function exactStoredF32Class(localPositions: Float32Array, exactLocalPosition: NativeLandmarkPoint): number[] {
  if (!(localPositions instanceof Float32Array) || localPositions.length % 3 || !finiteTuple(exactLocalPosition, 3)) {
    throw new TypeError('An exact native class requires packed Float32 XYZ and a finite unrounded query')
  }
  const members: number[] = []
  for (let offset = 0; offset < localPositions.length; offset += 3) {
    if (localPositions[offset] === exactLocalPosition[0] && localPositions[offset + 1] === exactLocalPosition[1]
      && localPositions[offset + 2] === exactLocalPosition[2]) members.push(offset / 3)
  }
  return members
}

/** Original topology only: a coincident row in another primitive earns no incidence. */
export function incidentOriginalTriangles(indices: Uint32Array, classVertexIds: readonly number[], vertexCount: number): NativeIncidentTriangle[] {
  if (!(indices instanceof Uint32Array) || indices.length % 3 || !Number.isSafeInteger(vertexCount) || vertexCount < 0
    || classVertexIds.some(id => !Number.isSafeInteger(id) || id < 0 || id >= vertexCount)
    || new Set(classVertexIds).size !== classVertexIds.length) throw new TypeError('Invalid native triangle topology or class')
  const members = new Set(classVertexIds)
  const triangles: NativeIncidentTriangle[] = []
  for (let offset = 0; offset < indices.length; offset += 3) {
    const a = indices[offset]!, b = indices[offset + 1]!, c = indices[offset + 2]!
    if (a >= vertexCount || b >= vertexCount || c >= vertexCount) throw new RangeError('Native index exceeds POSITION rows')
    if (members.has(a) || members.has(b) || members.has(c)) triangles.push({ triangleIndex: offset / 3, indexOffset: offset, vertexIds: [a, b, c] })
  }
  return triangles
}

export interface NativeStagePixelRay {
  nativeStageBackingPixel: NativeLandmarkPixel
  origin: NativeLandmarkPoint
  direction: NativeLandmarkPoint
  near: number
  far: number
}

/** GL lower-left pixel centres and actual camera matrices, not a source-ROI ray guess. */
export function deriveNativeStagePixelRay(draw: NativePrimitiveDraw, pixel: NativeLandmarkPixel): NativeStagePixelRay {
  const viewport = draw.viewportBackingPixels
  if (!finiteTuple(pixel, 2) || !pixel.every(Number.isSafeInteger) || !finiteTuple(viewport, 4)
    || viewport[2]! <= 0 || viewport[3]! <= 0 || pixel[0] < viewport[0]! || pixel[0] >= viewport[0]! + viewport[2]!
    || pixel[1] < viewport[1]! || pixel[1] >= viewport[1]! + viewport[3]!
    || !finiteTuple(draw.camera.projectionMatrixInverse, 16) || !finiteTuple(draw.camera.matrixWorld, 16)) {
    throw new RangeError('Native stage pixel or actual camera/viewport is unavailable')
  }
  const x = 2 * (pixel[0] + 0.5 - viewport[0]!) / viewport[2]! - 1
  const y = 2 * (pixel[1] + 0.5 - viewport[1]!) / viewport[3]! - 1
  const cameraPoint = transformPoint(draw.camera.projectionMatrixInverse, [x, y, 0.5])
  const worldPoint = transformPoint(draw.camera.matrixWorld, cameraPoint)
  const m = draw.camera.matrixWorld
  const origin: NativeLandmarkPoint = [m[12]!, m[13]!, m[14]!]
  const length = Math.hypot(worldPoint[0] - origin[0], worldPoint[1] - origin[1], worldPoint[2] - origin[2])
  const direction: NativeLandmarkPoint = [(worldPoint[0] - origin[0]) / length, (worldPoint[1] - origin[1]) / length, (worldPoint[2] - origin[2]) / length]
  const forwardLength = Math.hypot(m[8]!, m[9]!, m[10]!)
  const cameraDepthPerMetre = -(direction[0] * m[8]! + direction[1] * m[9]! + direction[2] * m[10]!) / forwardLength
  const near = draw.camera.near / cameraDepthPerMetre, far = draw.camera.far / cameraDepthPerMetre
  if (!finiteTuple(direction, 3) || !Number.isFinite(near) || !Number.isFinite(far) || !(near > 0 && far > near)) {
    throw new RangeError('Native perspective clip interval cannot be derived')
  }
  return { nativeStageBackingPixel: pixel, origin, direction, near, far }
}

export interface NativeCpuSurfaceHit extends NativeIncidentTriangle {
  primitiveId: string
  identity: NativePrimitiveIdentity
  scope: 'artifact' | 'runtime-clone'
  runtimeInstance: { instancePath: string; sourcePartPath: string } | null
  materialUuid: string
  distanceMetres: number
  barycentric: NativeLandmarkPoint
  worldPointMetres: NativeLandmarkPoint
  /** Distance from this queried ray's first-hit point to the exact class, not vertex arithmetic error. */
  targetResidualMetres: number
  targetClassIncident: boolean
}

/** Shape emitted by CurrentFirstSurface.guard; the envelope below binds its otherwise unbound draw. */
export interface NativeCpuSurfaceGuardResult {
  eligibilityScope: 'queried-ray-exact-vertex-identity'
  eligibility: 'eligible-cpu-exact-local-class' | 'ineligible-first-surface' | 'ambiguous-coincident-first-surfaces' | 'no-positive-surface'
  targetPrimitiveId: string
  targetLocalCoordinate: NativeLandmarkPoint
  classVertexIds: readonly number[]
  geometricResidualToleranceMetres: number
  firstHit: NativeCpuSurfaceHit | null
  coincidentClosestHits: readonly NativeCpuSurfaceHit[]
  scope: {
    primitiveCount: number; artifactPrimitiveCount: number; runtimeClonePrimitiveCount: number; springPrimitiveCount: number
    drawSubmissionCount: number; limitations: readonly unknown[]; rayProofLimited: boolean
  }
  safety: {
    sourceQualification: 'not-performed'; gpuSafety: 'unmeasured-independent-proof-required'
    worldCoordinatePrecision: 'float64-cpu-not-exact-gpu'; gpuRoundingBoundMetres: null
    rasterFirstSurfaceCertificate: false; genericApproval: false
  }
}

export interface NativeLandmarkBufferReceipt {
  primitiveId: string
  name: keyof NativePrimitiveBuffers
  arrayType: 'Float32Array' | 'Uint32Array' | 'Float64Array'
  byteLength: number
  sha256: string
}

export interface NativeCpuSurfaceEvidence {
  metadata: NativePrimitiveSubmissionMetadata
  ray: NativeStagePixelRay
  /** SHA receipts for every artifact/clone's packed local, index and world geometry. */
  bufferReceipts: readonly NativeLandmarkBufferReceipt[]
  result: NativeCpuSurfaceGuardResult
}

export interface NativeLandmarkProjectionEvidence {
  metadata: NativePrimitiveSubmissionMetadata
  capture: RenderedLandmarks
  anchor: LandmarkAnchor
}

/** Supplied only by a separately measured GPU-position control, never by the CPU guard or depth/ID pass. */
export interface IndependentNativeGpuPositionProof {
  method: 'independent-gpu-position-and-residual-bound'
  status: 'bounded' | 'unavailable' | 'unsupported'
  measurement: 'gpu-position-readback' | 'validated-gpu-arithmetic-bound'
  evidenceSha256: string
  controlEvidenceSha256: string
  metadata: NativePrimitiveSubmissionMetadata
  bufferReceipts: readonly NativeLandmarkBufferReceipt[]
  targetPrimitiveId: string
  exactLocalPosition: NativeLandmarkPoint
  classVertexIds: readonly number[]
  nativeStageBackingPixel: NativeLandmarkPixel
  gpuRoundingBoundMetres: number | null
  numericVertexResidualBoundMetres: number | null
}

function finiteTuple(value: readonly number[], length: number): boolean {
  return Array.isArray(value) && value.length === length && value.every(Number.isFinite)
}
function transformPoint(matrix: readonly number[], point: NativeLandmarkPoint): NativeLandmarkPoint {
  const [x, y, z] = point
  const w = matrix[3]! * x + matrix[7]! * y + matrix[11]! * z + matrix[15]!
  if (!Number.isFinite(w) || w === 0) throw new RangeError('Native camera homogeneous coordinate is invalid')
  return [(matrix[0]! * x + matrix[4]! * y + matrix[8]! * z + matrix[12]!) / w,
    (matrix[1]! * x + matrix[5]! * y + matrix[9]! * z + matrix[13]!) / w,
    (matrix[2]! * x + matrix[6]! * y + matrix[10]! * z + matrix[14]!) / w]
}

/** Structural identity, with no epsilon, omitted-key equivalence or JSON key-order dependence. */
function sameEvidence(left: unknown, right: unknown): boolean {
  if (left === right) return true
  if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') return false
  if (Array.isArray(left) !== Array.isArray(right)) return false
  const leftKeys = Object.keys(left), rightKeys = Object.keys(right)
  if (leftKeys.length !== rightKeys.length) return false
  const a = left as Record<string, unknown>, b = right as Record<string, unknown>
  return leftKeys.every(key => Object.hasOwn(b, key) && sameEvidence(a[key], b[key]))
}

function closedSnapshotReason(snapshot: CapturedSnapshot, metadata: CurrentMetadata): string | null {
  const manifest = snapshot.manifest, draw = manifest.draw, model = manifest.model, census = manifest.census
  if (manifest.schemaVersion !== 1 || manifest.method !== 'current-native-cpu-geometry'
    || manifest.worldCoordinatePrecision !== 'float64-cpu-not-exact-gpu'
    || manifest.geometricResidualToleranceMetres !== NATIVE_LANDMARK_GEOMETRIC_TOLERANCE_METRES
    || manifest.bufferEncoding !== 'typed-arrays-packed-xyz-no-welding'
    || !['little-endian', 'big-endian'].includes(manifest.bufferByteOrder)
    || manifest.issues.bindingFailures.length || manifest.issues.currentOverrideMisses.length) return 'unsupported-or-unbound-native-snapshot'
  if (!Number.isSafeInteger(metadata.inventoryRevision) || metadata.inventoryRevision < 0
    || !('inventoryRevision' in manifest) || manifest.inventoryRevision !== metadata.inventoryRevision) return 'missing-or-mismatched-inventory-revision'
  if (!Number.isSafeInteger(manifest.machineRevision) || manifest.machineRevision < 0
    || !Number.isSafeInteger(draw.drawRevision) || draw.drawRevision < 0
    || !Number.isSafeInteger(draw.contextRevision) || draw.contextRevision < 0
    || !draw.viewId || !(draw.timeSeconds === null || Number.isFinite(draw.timeSeconds))
    || !model.runtimeRootUuid || model.provenance.identity !== 'matched'
    || !/^[a-f0-9]{64}$/.test(model.provenance.sourceSha256)
    || !/^[a-f0-9]{64}$/.test(model.provenance.observedSha256 ?? '')
    || model.provenance.expectedSha256 !== model.provenance.observedSha256
    || !/^[a-f0-9]{64}$/.test(model.identityMapSha256) || !/^[a-f0-9]{64}$/.test(model.canonicalModelSha256)
    || !/^[a-f0-9]{64}$/.test(model.semanticSha256)) return 'missing-native-state-identity'
  if (!sameEvidence(model, metadata.model) || manifest.machineRevision !== metadata.machineRevision
    || !sameEvidence(manifest.input, metadata.input) || !sameEvidence(draw, metadata.draw)
    || !sameEvidence(census, metadata.census) || !sameEvidence(manifest.runtimeInstanceDeclarations, metadata.runtimeInstanceDeclarations)) {
    return 'stale-or-asymmetric-native-state'
  }
  const rows = [...manifest.primitives, ...manifest.runtimeClones]
  const ids = new Set<string>()
  let springs = 0, artifactSprings = 0, cloneSprings = 0
  for (const row of rows) {
    if (!row.id || ids.has(row.id)) return 'nonunique-native-primitive'
    ids.add(row.id)
    if (row.deformation.kind === 'native-stock-spring') {
      springs++
      if (row.scope === 'artifact') artifactSprings++
      else cloneSprings++
    } else if (row.deformation.kind !== 'matrix-only') return 'unsupported-native-deformation'
    const buffers = snapshot.buffers[row.id]
    if (!buffers || !(buffers.localPositions instanceof Float32Array) || !(buffers.indices instanceof Uint32Array)
      || !(buffers.worldPositions instanceof Float64Array) || buffers.localPositions.length !== row.vertexCount * 3
      || buffers.indices.length !== row.indexCount || buffers.worldPositions.length !== row.vertexCount * 3
      || row.decodedPosition.componentType !== 'Float32' || row.decodedPosition.itemSize !== 3 || row.decodedPosition.normalized !== false
      || !buffers.localPositions.every(Number.isFinite) || !buffers.worldPositions.every(Number.isFinite)
      || buffers.indices.some(index => index >= row.vertexCount)
      || !finiteTuple(row.matrixWorld, 16) || !row.objectUuid || !row.geometryUuid) return 'invalid-native-buffer-identity'
  }
  if (Object.keys(snapshot.buffers).length !== rows.length
    || manifest.primitives.some(row => row.scope !== 'artifact') || manifest.runtimeClones.some(row => row.scope !== 'runtime-clone')
    || manifest.primitives.length !== census.artifactPrimitiveCount || manifest.runtimeClones.length !== census.runtimeClonePrimitiveCount
    || springs !== census.springPrimitiveCount || artifactSprings !== census.artifactSpringPrimitiveCount
    || cloneSprings !== census.runtimeCloneSpringPrimitiveCount) return 'incomplete-native-artifact-clone-spring-census'
  return null
}

async function bufferReceiptReason(snapshot: CapturedSnapshot, receipts: readonly NativeLandmarkBufferReceipt[]): Promise<string | null> {
  const seen = new Set<string>()
  if (!globalThis.crypto?.subtle) return 'native-buffer-sha256-unavailable'
  for (const receipt of receipts) {
    const key = `${receipt.primitiveId}/${receipt.name}`
    const buffer = snapshot.buffers[receipt.primitiveId]?.[receipt.name]
    if (seen.has(key) || !buffer || buffer.constructor.name !== receipt.arrayType || buffer.byteLength !== receipt.byteLength
      || !/^[a-f0-9]{64}$/.test(receipt.sha256)) return 'invalid-or-duplicate-cpu-buffer-receipt'
    seen.add(key)
    const bytes = buffer.buffer instanceof ArrayBuffer
      ? new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength)
      : new Uint8Array(new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength))
    const digest = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes))
    const actual = Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('')
    if (actual !== receipt.sha256) return 'cpu-buffer-sha256-mismatch'
  }
  for (const id of Object.keys(snapshot.buffers)) {
    if (!seen.has(`${id}/localPositions`) || !seen.has(`${id}/indices`) || !seen.has(`${id}/worldPositions`)) {
      return 'incomplete-full-scope-cpu-buffer-receipts'
    }
  }
  return null
}

function hitTopologyReason(hit: NativeCpuSurfaceHit, row: NativePrimitiveManifest, buffers: NativePrimitiveBuffers): string | null {
  if (!sameEvidence(hit.identity, row.identity) || hit.scope !== row.scope || !sameEvidence(hit.runtimeInstance, row.runtimeInstance)
    || !Number.isSafeInteger(hit.indexOffset) || hit.indexOffset < 0 || hit.indexOffset % 3
    || hit.indexOffset + 2 >= buffers.indices.length || hit.triangleIndex !== hit.indexOffset / 3
    || !sameEvidence(hit.vertexIds, [buffers.indices[hit.indexOffset], buffers.indices[hit.indexOffset + 1], buffers.indices[hit.indexOffset + 2]])) {
    return 'cpu-hit-original-topology-mismatch'
  }
  const start = row.drawRange.effectiveStart, end = start + row.drawRange.effectiveCount
  if (row.drawMode !== 'triangles' || row.renderedPresence !== 'native-render-callback-observed'
    || hit.indexOffset < start || hit.indexOffset + 3 > end
    || !row.renderSubmissions.some(submission => submission.objectUuid === row.objectUuid && submission.materialUuid === hit.materialUuid
      && (!submission.group || (hit.indexOffset >= submission.group.start && hit.indexOffset + 3 <= submission.group.start + submission.group.count)))) {
    return 'cpu-hit-not-in-actual-submitted-topology'
  }
  return null
}

function exactClassWorldResidual(worldPositions: Float64Array, classVertexIds: readonly number[], point: NativeLandmarkPoint): number {
  let residual = Infinity
  for (const id of classVertexIds) {
    const offset = id * 3
    residual = Math.min(residual, Math.hypot(worldPositions[offset]! - point[0], worldPositions[offset + 1]! - point[1], worldPositions[offset + 2]! - point[2]))
  }
  return residual
}

export interface NativeLandmarkEligibilityInput {
  snapshot: NativePrimitiveSnapshot | null
  currentMetadata: NativePrimitiveSubmissionMetadata | null
  target: { primitiveId: string; exactLocalPosition: NativeLandmarkPoint; nativeStageBackingPixel: NativeLandmarkPixel } | null
  projection: NativeLandmarkProjectionEvidence | null
  cpu: NativeCpuSurfaceEvidence | null
  gpu: NativeTargetSurfaceReadback | null
  independentGpuProof: IndependentNativeGpuPositionProof | null
}

export interface NativeLandmarkEligibilityResult {
  method: 'current-exact-native-landmark-evidence-join'
  eligibilityScope: typeof NATIVE_LANDMARK_ELIGIBILITY_SCOPE
  state: 'eligible' | 'ineligible' | 'unresolved'
  reasons: readonly string[]
  qualification: 'selected-pixel-exact-vertex-identity-not-general-landmark-validity-or-source-acceptance'
  sourceProof: false
  sourceAcceptance: false
  geometricResidualToleranceMetres: 1e-7
  target: NativeLandmarkEligibilityInput['target']
  classVertexIds: readonly number[]
  incidentTriangles: readonly NativeIncidentTriangle[]
  /** Selected pixel-centre hit-to-class distance; a miss does not invalidate the native anchor. */
  cpuGeometricResidualMetres: number | null
  gpuRoundingBoundMetres: number | null
  numericVertexResidualBoundMetres: number | null
  combinedGpuVertexBoundMetres: number | null
  /** Raw depth-off projection and independent uncertainties survive every refusal. */
  measurements: {
    projection: NativeLandmarkProjectionEvidence | null
    cpu: NativeCpuSurfaceEvidence | null
    gpu: NativeTargetSurfaceReadback | null
    independentGpuProof: IndependentNativeGpuPositionProof | null
  }
}

/** Selected-pixel verification consumer only; never a general landmark-visibility or playback gate. */
export async function joinNativeLandmarkEligibility(input: NativeLandmarkEligibilityInput): Promise<NativeLandmarkEligibilityResult> {
  let classVertexIds: number[] = [], incidentTriangles: NativeIncidentTriangle[] = []
  let cpuGeometricResidualMetres: number | null = null
  let gpuRoundingBoundMetres: number | null = null, numericVertexResidualBoundMetres: number | null = null
  const finish = (state: NativeLandmarkEligibilityResult['state'], ...reasons: string[]): NativeLandmarkEligibilityResult => ({
    method: 'current-exact-native-landmark-evidence-join', eligibilityScope: NATIVE_LANDMARK_ELIGIBILITY_SCOPE, state, reasons,
    qualification: 'selected-pixel-exact-vertex-identity-not-general-landmark-validity-or-source-acceptance', sourceProof: false, sourceAcceptance: false,
    geometricResidualToleranceMetres: 1e-7, target: input.target, classVertexIds, incidentTriangles, cpuGeometricResidualMetres,
    gpuRoundingBoundMetres, numericVertexResidualBoundMetres,
    combinedGpuVertexBoundMetres: gpuRoundingBoundMetres === null || numericVertexResidualBoundMetres === null
      ? null : gpuRoundingBoundMetres + Math.max(cpuGeometricResidualMetres ?? 0, numericVertexResidualBoundMetres),
    measurements: { projection: input.projection, cpu: input.cpu, gpu: input.gpu, independentGpuProof: input.independentGpuProof },
  })
  try {
    const { snapshot, currentMetadata: metadata, projection, cpu, gpu, independentGpuProof: proof, target } = input
    if (!target) return finish('unresolved', 'missing-unique-native-target-or-unwarped-stage-pixel-authority')
    if (!snapshot || snapshot.status !== 'captured') return finish('unresolved', 'missing-or-stale-current-native-snapshot')
    if (!metadata || metadata.status !== 'current-diagnostic-submission') return finish('unresolved', 'missing-or-stale-current-native-metadata')
    const closedReason = closedSnapshotReason(snapshot, metadata)
    if (closedReason) return finish('unresolved', closedReason)
    const manifest = snapshot.manifest, rows = [...manifest.primitives, ...manifest.runtimeClones]
    const row = rows.find(primitive => primitive.id === target.primitiveId), buffers = snapshot.buffers[target.primitiveId]
    if (!row || !buffers) return finish('unresolved', 'target-unique-native-primitive-not-captured')
    if (row.drawMode !== 'triangles' || row.identity.gltfMode !== 4) return finish('unresolved', 'unsupported-target-native-draw-mode')
    classVertexIds = exactStoredF32Class(buffers.localPositions, target.exactLocalPosition)
    if (!classVertexIds.length) return finish('ineligible', 'target-is-not-an-exact-stored-f32-class')
    incidentTriangles = incidentOriginalTriangles(buffers.indices, classVertexIds, row.vertexCount)
    if (!incidentTriangles.length) return finish('ineligible', 'target-class-has-no-original-incident-triangle')
    if (!projection) return finish('unresolved', 'missing-current-depth-off-projection')
    if (!sameEvidence(projection.metadata, metadata)) return finish('unresolved', 'stale-or-asymmetric-projection-state')
    const capture = projection.capture, anchor = projection.anchor
    const markers = capture.landmarks.filter(marker => marker.id === anchor.id)
    const marker = markers[0], partPath = row.runtimeInstance?.instancePath ?? row.identity.nodePath
    const templatePath = row.runtimeInstance?.sourcePartPath ?? null
    if (markers.length !== 1 || !marker || anchor.partPath !== partPath || (anchor.runtimeTemplatePartPath ?? null) !== templatePath
      || !sameEvidence(anchor.partLocalMetres, target.exactLocalPosition) || anchor.worldMetres !== undefined
      || marker.partPath !== partPath || marker.runtimeTemplatePartPath !== templatePath) {
      return finish('unresolved', 'projection-anchor-unique-native-class-association-mismatch')
    }
    if (capture.method !== 'gpu-readback' || capture.status !== 'captured' || capture.visibilityMode !== 'depth-off-landmark-projection'
      || capture.viewId !== metadata.draw.viewId || capture.timeSeconds !== metadata.draw.timeSeconds
      || capture.presentation !== metadata.draw.presentation || capture.sourceOpacity !== metadata.draw.sourceOpacity
      || !sameEvidence(capture.sourceAssembly, metadata.draw.sourceAssembly) || !sameEvidence(capture.sourceLayout, metadata.draw.sourceLayout)
      || !sameEvidence(capture.resolvedImagePlaneWarp, metadata.draw.imagePlaneWarp)
      || !sameEvidence(capture.nativeViewportBackingPixels,
        metadata.draw.imagePlaneWarp ? metadata.draw.viewportBackingPixels.slice(2) : null)) {
      return finish('unresolved', 'projection-current-draw-identity-mismatch')
    }
    if (marker.state === 'unresolved') return finish('unresolved', 'depth-off-projection-unresolved')
    if (marker.state !== 'rendered' || capture.sourceOpacity <= 0) return finish('ineligible', 'depth-off-projection-has-no-source-contribution')
    if (!marker.worldMetres || !finiteTuple(marker.worldMetres, 3) || !marker.sourcePixels || !finiteTuple(marker.sourcePixels, 2)
      || !marker.canvasPixels || !finiteTuple(marker.canvasPixels, 2)
      || marker.uncertaintySourcePixels === null || !Number.isFinite(marker.uncertaintySourcePixels) || marker.uncertaintySourcePixels < 0
      || marker.uncertaintyCanvasPixels === null || !Number.isFinite(marker.uncertaintyCanvasPixels) || marker.uncertaintyCanvasPixels < 0) {
      return finish('unresolved', 'missing-raw-projection-or-independent-raster-uncertainty')
    }
    const markerWorldResidual = exactClassWorldResidual(buffers.worldPositions, classVertexIds, marker.worldMetres)
    if (markerWorldResidual > NATIVE_LANDMARK_GEOMETRIC_TOLERANCE_METRES) return finish('ineligible', 'projection-world-point-is-not-current-target-class')
    if (!cpu) return finish('unresolved', 'missing-full-scope-cpu-first-surface-evidence')
    if (!sameEvidence(cpu.metadata, metadata)) return finish('unresolved', 'stale-or-asymmetric-cpu-state')
    const derivedRay = deriveNativeStagePixelRay(metadata.draw, target.nativeStageBackingPixel)
    if (!sameEvidence(cpu.ray, derivedRay)) return finish('unresolved', 'cpu-ray-is-not-the-current-unwarped-native-stage-pixel')
    const receiptReason = await bufferReceiptReason(snapshot, cpu.bufferReceipts)
    if (receiptReason) return finish('unresolved', receiptReason)
    const guard = cpu.result, scope = guard.scope
    if (guard.eligibilityScope !== 'queried-ray-exact-vertex-identity') {
      return finish('unresolved', 'missing-or-unsupported-cpu-query-eligibility-scope')
    }
    if (!['eligible-cpu-exact-local-class', 'ineligible-first-surface', 'ambiguous-coincident-first-surfaces', 'no-positive-surface'].includes(guard.eligibility)) {
      return finish('unresolved', 'unsupported-cpu-first-surface-result-mode')
    }
    if (guard.targetPrimitiveId !== row.id || !sameEvidence(guard.targetLocalCoordinate, target.exactLocalPosition)
      || !sameEvidence(guard.classVertexIds, classVertexIds)
      || guard.geometricResidualToleranceMetres !== NATIVE_LANDMARK_GEOMETRIC_TOLERANCE_METRES
      || guard.safety.worldCoordinatePrecision !== 'float64-cpu-not-exact-gpu' || guard.safety.gpuRoundingBoundMetres !== null
      || guard.safety.rasterFirstSurfaceCertificate !== false || guard.safety.genericApproval !== false
      || guard.safety.sourceQualification !== 'not-performed' || guard.safety.gpuSafety !== 'unmeasured-independent-proof-required') {
      return finish('unresolved', 'cpu-target-class-or-independent-budget-contract-mismatch')
    }
    if (scope.primitiveCount !== rows.length || scope.artifactPrimitiveCount !== manifest.census.artifactPrimitiveCount
      || scope.runtimeClonePrimitiveCount !== manifest.census.runtimeClonePrimitiveCount || scope.springPrimitiveCount !== manifest.census.springPrimitiveCount) {
      return finish('unresolved', 'incomplete-cpu-first-surface-artifact-clone-spring-scope')
    }
    if (scope.rayProofLimited !== false || scope.limitations.length) return finish('unresolved', 'unsupported-full-scope-cpu-raster-or-deformation-mode')
    if (!sameEvidence(guard.firstHit, guard.coincidentClosestHits[0] ?? null)) return finish('unresolved', 'cpu-first-surface-hit-set-mismatch')
    let cpuNegative: string | null = guard.coincidentClosestHits.length ? null : 'cpu-no-positive-first-surface'
    let maximumResidual = 0
    for (const hit of guard.coincidentClosestHits) {
      const hitRow = rows.find(primitive => primitive.id === hit.primitiveId), hitBuffers = snapshot.buffers[hit.primitiveId]
      if (!hitRow || !hitBuffers) return finish('unresolved', 'cpu-first-surface-primitive-not-in-full-scope')
      const topologyReason = hitTopologyReason(hit, hitRow, hitBuffers)
      if (topologyReason) return finish('unresolved', topologyReason)
      if (!finiteTuple(hit.worldPointMetres, 3) || !finiteTuple(hit.barycentric, 3)
        || !Number.isFinite(hit.distanceMetres) || !(hit.distanceMetres > 0 && hit.distanceMetres >= derivedRay.near && hit.distanceMetres <= derivedRay.far)
        || hit.distanceMetres !== guard.firstHit?.distanceMetres
        || !Number.isFinite(hit.targetResidualMetres) || hit.targetResidualMetres < 0) return finish('unresolved', 'invalid-cpu-first-surface-measurement')
      const actualResidual = exactClassWorldResidual(buffers.worldPositions, classVertexIds, hit.worldPointMetres)
      // Replay arithmetic only; this does not enlarge the independent 1e-7 geometry budget.
      const rayX = derivedRay.origin[0] + derivedRay.direction[0] * hit.distanceMetres
      const rayY = derivedRay.origin[1] + derivedRay.direction[1] * hit.distanceMetres
      const rayZ = derivedRay.origin[2] + derivedRay.direction[2] * hit.distanceMetres
      const replayScale = Math.max(1, Math.abs(rayX), Math.abs(rayY), Math.abs(rayZ),
        Math.abs(hit.worldPointMetres[0]), Math.abs(hit.worldPointMetres[1]), Math.abs(hit.worldPointMetres[2]))
      if (Math.hypot(rayX - hit.worldPointMetres[0], rayY - hit.worldPointMetres[1], rayZ - hit.worldPointMetres[2]) > Number.EPSILON * replayScale * 8) {
        return finish('unresolved', 'cpu-first-surface-point-is-not-on-the-current-pixel-ray')
      }
      const incident = hit.primitiveId === row.id && hit.vertexIds.some(id => classVertexIds.includes(id))
      if (hit.targetClassIncident !== incident || Math.abs(actualResidual - hit.targetResidualMetres) > Number.EPSILON * Math.max(1, actualResidual) * 8) {
        return finish('unresolved', 'cpu-first-surface-residual-or-class-measurement-mismatch')
      }
      maximumResidual = Math.max(maximumResidual, actualResidual)
      if (hit.primitiveId !== row.id) cpuNegative = 'cpu-occluded-by-other-native-primitive'
      else if (!incident) cpuNegative = 'cpu-first-surface-is-adjacent-nonclass-triangle'
      else if (actualResidual > NATIVE_LANDMARK_GEOMETRIC_TOLERANCE_METRES) cpuNegative = 'cpu-selected-pixel-first-surface-exceeds-exact-vertex-residual'
    }
    cpuGeometricResidualMetres = guard.coincidentClosestHits.length ? maximumResidual : null
    if ((guard.eligibility === 'eligible-cpu-exact-local-class') !== (cpuNegative === null)) {
      return finish('unresolved', 'cpu-first-surface-eligibility-contradicts-measurements')
    }
    if (gpu && gpu.status !== 'readback') return finish('unresolved', 'missing-or-stale-actual-gpu-target-association')
    if (!gpu) return cpuNegative ? finish('ineligible', cpuNegative) : finish('unresolved', 'missing-or-stale-actual-gpu-target-association')
    if (gpu.method !== 'current-native-depth-target-surface-association' || gpu.equivalence !== 'depth-native-not-colour-or-composite'
      || gpu.sourceProof !== false || gpu.sourceAcceptance !== false || gpu.numericVertexResidualBoundMetres !== null
      || gpu.gpuPositionRoundingBoundMetres !== null || gpu.eligibility !== 'unresolved'
      || !sameEvidence(gpu.model, metadata.model) || gpu.machineRevision !== metadata.machineRevision || gpu.inventoryRevision !== metadata.inventoryRevision
      || !sameEvidence(gpu.input, metadata.input) || !sameEvidence(gpu.draw, metadata.draw) || !sameEvidence(gpu.census, metadata.census)
      || !sameEvidence(gpu.runtimeInstanceDeclarations, metadata.runtimeInstanceDeclarations)) return finish('unresolved', 'stale-or-asymmetric-gpu-target-state')
    const request = gpu.request, association = gpu.association, gpuTarget = gpu.target
    if (association.sourceProof !== false || association.sourceAcceptance !== false || association.numericVertexResidualBoundMetres !== null
      || association.gpuPositionRoundingBoundMetres !== null || association.eligibility !== 'unresolved') {
      return finish('unresolved', 'gpu-depth-id-readback-is-not-an-independent-vertex-bound')
    }
    const offsets = incidentTriangles.map(triangle => triangle.indexOffset)
    if (request.expectedDrawRevision !== metadata.draw.drawRevision || request.expectedContextRevision !== metadata.draw.contextRevision
      || request.expectedViewId !== metadata.draw.viewId || request.expectedTimeSeconds !== metadata.draw.timeSeconds
      || request.targetPrimitiveId !== row.id || !sameEvidence(request.exactLocalPosition, target.exactLocalPosition)
      || !sameEvidence(request.nativeStageBackingPixel, target.nativeStageBackingPixel)
      || !sameEvidence(gpuTarget.record, row) || gpuTarget.primitiveId !== row.id || gpuTarget.canonicalPrimitiveId !== row.identity.canonicalId
      || !sameEvidence(gpuTarget.classVertexIndices, classVertexIds) || !sameEvidence(gpuTarget.incidentTriangleIndexOffsets, offsets)
      || !sameEvidence(association.targetClassVertexIndices, classVertexIds) || !sameEvidence(association.incidentTriangleIndexOffsets, offsets)
      || !offsets.includes(request.targetIndexOffset) || association.requestedTriangleIndexOffset !== request.targetIndexOffset) {
      return finish('unresolved', 'gpu-target-unique-primitive-class-or-original-topology-mismatch')
    }
    const stage = gpu.nativeStage, draw = metadata.draw
    if (stage.width !== (draw.renderTarget?.width ?? draw.canvas.width) || stage.height !== (draw.renderTarget?.height ?? draw.canvas.height)
      || !sameEvidence(stage.viewportBackingPixels, draw.viewportBackingPixels) || !sameEvidence(stage.scissorBackingPixels, draw.scissorBackingPixels)
      || stage.scissorTest !== draw.scissorTest || !sameEvidence(stage.pixelCentreBacking, [target.nativeStageBackingPixel[0] + 0.5, target.nativeStageBackingPixel[1] + 0.5])
      || association.rawPixel.length !== 4 || association.rawPixel.some(byte => !Number.isInteger(byte) || byte < 0 || byte > 255)) {
      return finish('unresolved', 'gpu-native-stage-pixel-or-rgba8-identity-mismatch')
    }
    if (association.status === 'unresolved') return finish('unresolved', 'actual-gpu-target-association-unresolved')
    if (cpuNegative) return finish('ineligible', cpuNegative)
    if (association.status === 'occluded-by-native-primitive') {
      if (!association.primitiveId || association.primitiveId === row.id || !rows.some(primitive => primitive.id === association.primitiveId)) {
        return finish('unresolved', 'gpu-occluder-identity-mismatch')
      }
      return finish('ineligible', 'gpu-occluded-by-other-native-primitive')
    }
    if (association.status === 'no-native-surface') return finish('ineligible', 'gpu-no-native-first-surface')
    if (association.primitiveId !== row.id || association.canonicalPrimitiveId !== row.identity.canonicalId) return finish('ineligible', 'gpu-first-surface-wrong-native-primitive')
    if (association.status === 'target-other-triangle' || association.triangleIndexOffset === null || !offsets.includes(association.triangleIndexOffset)) {
      return finish('ineligible', 'gpu-first-surface-is-adjacent-nonclass-triangle')
    }
    if (association.status !== 'target-incident-triangle' || association.rawPixel[3] !== 255) return finish('unresolved', 'unsupported-gpu-target-association-mode')
    if (!proof) return finish('unresolved', 'independent-gpu-rounding-bound-not-supplied', 'independent-gpu-vertex-residual-bound-not-supplied')
    if (proof.status !== 'bounded' || proof.method !== 'independent-gpu-position-and-residual-bound'
      || !['gpu-position-readback', 'validated-gpu-arithmetic-bound'].includes(proof.measurement)
      || !/^[a-f0-9]{64}$/.test(proof.evidenceSha256) || !/^[a-f0-9]{64}$/.test(proof.controlEvidenceSha256)
      || proof.evidenceSha256 === proof.controlEvidenceSha256) return finish('unresolved', 'independent-gpu-position-proof-unavailable-or-unsupported')
    if (!sameEvidence(proof.metadata, metadata) || proof.targetPrimitiveId !== row.id || !sameEvidence(proof.exactLocalPosition, target.exactLocalPosition)
      || !sameEvidence(proof.classVertexIds, classVertexIds) || !sameEvidence(proof.nativeStageBackingPixel, target.nativeStageBackingPixel)
      || !sameEvidence(proof.bufferReceipts, cpu.bufferReceipts)) return finish('unresolved', 'stale-or-asymmetric-independent-gpu-position-proof')
    const missingBounds: string[] = []
    if (proof.gpuRoundingBoundMetres === null || !Number.isFinite(proof.gpuRoundingBoundMetres) || proof.gpuRoundingBoundMetres < 0) missingBounds.push('independent-gpu-rounding-bound-not-supplied')
    if (proof.numericVertexResidualBoundMetres === null || !Number.isFinite(proof.numericVertexResidualBoundMetres) || proof.numericVertexResidualBoundMetres < 0) missingBounds.push('independent-gpu-vertex-residual-bound-not-supplied')
    if (missingBounds.length) return finish('unresolved', ...missingBounds)
    gpuRoundingBoundMetres = proof.gpuRoundingBoundMetres
    numericVertexResidualBoundMetres = proof.numericVertexResidualBoundMetres
    if (gpuRoundingBoundMetres! + Math.max(cpuGeometricResidualMetres ?? 0, numericVertexResidualBoundMetres!) > NATIVE_LANDMARK_GEOMETRIC_TOLERANCE_METRES) {
      return finish('ineligible', 'independently-bounded-gpu-position-exceeds-geometric-budget')
    }
    return finish('eligible', 'current-exact-class-first-surface-and-independent-gpu-position-bound')
  } catch (error) {
    return finish('unresolved', `malformed-or-unsupported-native-landmark-evidence:${error instanceof Error ? error.message : String(error)}`)
  }
}
