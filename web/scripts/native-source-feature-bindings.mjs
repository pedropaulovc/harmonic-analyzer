import { PerspectiveCamera, Vector3 } from 'three'
import { canonicalJson, jsonDigest, sha256 } from './native-model-byte-proof.mjs'
import { nativeAnchorError, nativeBodyAssociationIndex, resolveNativeBodyAssociation, invertHomography, projectHomography, frameViews, visibilityProofErrors, witnessErrors } from './verify-reference.mjs'
import { freezeIntroSilverHeadWitnesses, verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'
import { serializeNativeBinding } from '../native-qualification-contract.mjs'

const clone = value => JSON.parse(canonicalJson(value))
const same = (a, b) => canonicalJson(a) === canonicalJson(b)
const point = (value, count) => Array.isArray(value) && value.length === count && value.every(Number.isFinite)
function freeze(value) {
  if (value && typeof value === 'object' && !ArrayBuffer.isView(value) && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) freeze(item)
    Object.freeze(value)
  }
  return value
}
function sourceTuple(record, frame, view, binding) {
  return { sourceVideoId: record.id, sourceSha256: record.native.observedSha256, sourceImage: clone(frame.sourceImage),
    decodedFrameIndex: frame.sourceImage.frameIndex, decodedTimestampTicks: binding.decodedTimestampTicks, timeBase: binding.timeBase,
    decodedTimeSeconds: frame.decodedTimeSeconds, shotId: frame.shotId, viewId: view.id, originalViewId: view.originalViewId ?? view.id }
}
function originalFrames(record, frame) {
  return (record.observations?.frames ?? []).filter(original => original.shotId === frame.shotId
    && original.sourceImage?.frameIndex === frame.sourceImage.frameIndex && same(original.sourceImage, frame.sourceImage)
    && original.decodedTimeSeconds === frame.decodedTimeSeconds)
}

/** Reuse the established source certificate validator, with the independently
 * selected current tuple. A raw four-feature proof is never a full body census,
 * and absent/stale historical source certificates are not rewritten to pass. */
export function nativeSourceVisibilityExpectation({ record, frame, view, binding }) {
  const originalViewId = view.originalViewId ?? view.id
  const originalViews = originalFrames(record, frame).flatMap(original => frameViews(original).filter(sourceView => sourceView.id === originalViewId))
  const stateRows = originalViews.map(sourceView => sourceView.mechanicalState ?? null)
  const ambiguous = stateRows.length > 1 && stateRows.some(state => !same(state, stateRows[0]))
  const sourceMechanicalState = !ambiguous && stateRows.length ? stateRows[0] : null
  const status = sourceMechanicalState?.status ?? null
  const sourceRuntimeWitness = status === 'constrained' ? sourceMechanicalState.runtimeWitness ?? null : null
  const sourceVisibilityProof = status === 'constrained' ? sourceRuntimeWitness?.visibilityProof ?? null
    : status === 'observed' ? sourceMechanicalState.visibilityProof ?? null : null
  const expectedVisibilityBinding = {
    sourceVideoId: binding.sourceVideoId, sourceSha256: binding.sourceSha256, sourceImage: binding.sourceImage,
    modelSha256: binding.modelRawSHA256, modelSourceCommit: binding.modelSourceCommit, shotId: binding.shotId, viewId: binding.viewId,
    timeSeconds: binding.timeSeconds, decodedTimeSeconds: binding.decodedTimeSeconds, input: binding.input, camera: view.camera,
    rectSourcePixels: binding.rectSourcePixels, presentation: binding.presentation, imagePlaneWarp: binding.imagePlaneWarp,
    resolvedImagePlaneWarp: binding.resolvedImagePlaneWarp, sourceLayout: binding.sourceLayout, composite: binding.composite,
    partOverrides: binding.partOverrides, constraints: sourceRuntimeWitness?.constraints ?? [], continuity: sourceRuntimeWitness?.continuity ?? null,
    nativeGeometryAssumptions: record.observations.nativeGeometryAssumptions ?? [],
    sourceNonIdentifiableFixedParts: sourceVisibilityProof?.sourceNonIdentifiableFixedParts ?? [],
  }
  const originalLandmarks = originalFrames(record, frame).flatMap(original => (original.landmarks ?? []).filter(row => (row.viewId ?? 'main') === originalViewId))
  const sourceView = originalViews[0] ?? view
  const errors = status === 'constrained'
    ? witnessErrors(sourceRuntimeWitness, expectedVisibilityBinding, record.observations.anchors ?? [], originalLandmarks, sourceView)
    : visibilityProofErrors(sourceVisibilityProof, expectedVisibilityBinding, record.observations.anchors ?? [], originalLandmarks, sourceView)
  if (ambiguous) errors.push('Original exact-exposure source mechanical/visibility states are contradictory')
  if (!['observed', 'constrained'].includes(status)) errors.push('Original source view has no observed or constrained physical body certificate')
  return { sourceVisibilityProof, sourceRuntimeWitness, sourceMechanicalState, sourceMechanicalStateStatus: status,
    expectedVisibilityBinding, sourceVisibilityErrors: [...new Set(errors)] }
}
function sourcePixelToNative(pixel, binding, viewport) {
  let p
  const warp = binding.resolvedImagePlaneWarp
  if (warp) {
    p = projectHomography(invertHomography(warp.renderToSourcePixels), pixel)
    p = [p[0] / warp.unwarpedViewportPixels[0], p[1] / warp.unwarpedViewportPixels[1]]
  } else {
    const [x, y, width, height] = binding.rectSourcePixels
    p = [(pixel[0] - x) / width, (pixel[1] - y) / height]
  }
  if (!warp && binding.presentation === 'horizontal-mirror') p[0] = 1 - p[0]
  const result = [Math.floor(p[0] * viewport[0]), viewport[1] - 1 - Math.floor(p[1] * viewport[1])]
  return result.every((value, axis) => value >= 0 && value < viewport[axis]) ? result : null
}
function createFeatureProjector(binding, viewport) {
  const record = binding.camera, nominal = binding.resolvedImagePlaneWarp?.unwarpedViewportPixels ?? binding.rectSourcePixels.slice(2)
  const camera = new PerspectiveCamera(record.verticalFovDegrees, nominal[0] / nominal[1], 0.005, 100)
  camera.position.fromArray(record.positionMetres); camera.quaternion.fromArray(record.quaternion).normalize()
  const principal = record.principalPointViewportPixels
  if (principal) camera.setViewOffset(nominal[0], nominal[1], nominal[0] / 2 - principal[0], nominal[1] / 2 - principal[1], nominal[0], nominal[1])
  camera.updateProjectionMatrix(); camera.updateMatrixWorld(true)
  const projected = new Vector3()
  return (localPoint, posed) => {
    const matrix = posed.matrixWorld, [x, y, z] = localPoint
    projected.set(matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
      matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
      matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]).project(camera)
    if (projected.z < -1 || projected.z > 1) return null
    const pixel = [Math.floor((projected.x + 1) * viewport[0] / 2), Math.floor((projected.y + 1) * viewport[1] / 2)]
    return pixel.every((value, axis) => Number.isSafeInteger(value) && value >= 0 && value < viewport[axis]) ? pixel : null
  }
}
function adjacentTriangles(primitive, vertices) {
  const selected = new Set(vertices), indices = []
  for (let offset = 0; offset < primitive.index.length; offset += 3) {
    if (selected.has(primitive.index[offset]) || selected.has(primitive.index[offset + 1]) || selected.has(primitive.index[offset + 2])) indices.push(offset / 3)
  }
  return indices
}
/** Construct only a stored point or a closed triangle point. Coordinate origins
 * in a shaft cavity are not promoted to surface features by naming conventions. */
export function nativeWitnessAtOriginalPoint(primitive, localPoint, anchorId, sourceFeatureEvidenceSHA256) {
  if (!point(localPoint, 3)) throw new Error('Original feature lacks a finite native local point')
  const base = { anchorId, partPath: primitive.path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, sourceFeatureEvidenceSHA256 }
  for (let i = 0; i < primitive.positions.length / 3; i++) {
    if (localPoint.every((value, axis) => value === primitive.positions[i * 3 + axis])) {
      const witness = { ...base, kind: 'mesh-vertex', vertexIndex: i, adjacentTriangleIndices: adjacentTriangles(primitive, [i]) }
      verifyNativeMeshFeatureWitness(witness, primitive)
      return witness
    }
  }
  for (let offset = 0; offset < primitive.index.length; offset += 3) {
    const a = Array.from(primitive.positions.subarray(primitive.index[offset] * 3, primitive.index[offset] * 3 + 3))
    const b = Array.from(primitive.positions.subarray(primitive.index[offset + 1] * 3, primitive.index[offset + 1] * 3 + 3))
    const c = Array.from(primitive.positions.subarray(primitive.index[offset + 2] * 3, primitive.index[offset + 2] * 3 + 3))
    const u = b.map((v, i) => v - a[i]), v = c.map((v, i) => v - a[i]), p = localPoint.map((v, i) => v - a[i])
    const dot = (x, y) => x.reduce((sum, n, i) => sum + n * y[i], 0)
    const uu = dot(u, u), uv = dot(u, v), vv = dot(v, v), pu = dot(p, u), pv = dot(p, v), determinant = uu * vv - uv * uv
    if (!(determinant > 0)) continue
    const wb = (pu * vv - pv * uv) / determinant, wc = (pv * uu - pu * uv) / determinant, wa = 1 - wb - wc
    if ([wa, wb, wc].some(w => w < 0 || w > 1) || wa + wb + wc !== 1) continue
    // Roundoff of the arithmetic construction only, not a relaxed physical or
    // GPU tolerance. No nearest-triangle snap or user coordinate is substituted.
    const scale = Math.max(...a.map(Math.abs), ...b.map(Math.abs), ...c.map(Math.abs), Number.MIN_VALUE)
    if (localPoint.some((value, i) => Math.abs(a[i] + wb * u[i] + wc * v[i] - value) > Number.EPSILON * scale * 32)) continue
    const witness = { ...base, kind: 'triangle-point', triangleIndex: offset / 3, barycentric: [wa, wb, wc] }
    verifyNativeMeshFeatureWitness(witness, primitive)
    return witness
  }
  throw new Error('Original native coordinate has no genuine stored-vertex or triangle surface support')
}

/** Describe current raw typed bytes without retaining a primitive proof. */
export function describeRawNativePrimitive(primitive, indices) {
  const widths = { 1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4' }
  return { mode: 4, attributes: Object.fromEntries(Object.entries(primitive.attributes).map(([name, attribute]) => [name, {
    componentType: attribute.componentType, type: widths[attribute.itemSize], count: attribute.count, normalized: attribute.normalized,
    typedBytesSha256: sha256(attribute.bytes),
  }])), indices: { componentType: indices.componentType, type: 'SCALAR', count: indices.count, normalized: indices.normalized,
    typedBytesSha256: sha256(indices.bytes) }, material: primitive.material }
}

const primitiveProofs = new WeakMap()
function originalPrimitiveProof(primitive, nativeModel) {
  if (primitiveProofs.has(primitive)) return primitiveProofs.get(primitive)
  const rawPrimitive = nativeModel.document.meshes[primitive.meshIndex].primitives[primitive.primitiveIndex]
  const indices = nativeModel.accessor(rawPrimitive.indices)
  const descriptor = describeRawNativePrimitive(primitive, indices)
  primitiveProofs.set(primitive, descriptor)
  return descriptor
}
function proveOriginalAncestry(proof, primitive, originalNative, nativeModel) {
  if (!proof || (Object.hasOwn(proof, 'currentNodeIndex') && proof.currentNodeIndex !== primitive.nodeIndex)
    || !same(proof.currentWorldMatrix, Array.from(originalNative.restMatrixF64))
    || !Array.isArray(proof.primitives) || !proof.primitives.some(entry => same(entry, originalPrimitiveProof(primitive, nativeModel)))) {
    throw new Error('Original native association does not match actual raw attributes/topology/material and frozen CPU ancestry')
  }
}

/** Original pixel facts and admitted raw topology are independent of the browser
 * packet. Unsupported coordinates remain in the source unavailable ledger.
 * `sourceInspection` must be the real retained primary inspection artifact; the
 * four original FIT observations alone cannot manufacture its authority. */
export function createNativeSourceFeatureBindings({ nativeModel, poseOracle, sourceInspection = null }) {
  if (!(nativeModel?.primitives instanceof Map) || !poseOracle?.inventory || !poseOracle.solve) throw new Error('Independent original raw/CPU feature authority required')
  const intro = sourceInspection ? freezeIntroSilverHeadWitnesses(nativeModel, sourceInspection) : []
  const introByAnchor = new Map(intro.map(row => [row.witness.anchorId, row]))
  const originalByPath = new Map(poseOracle.inventory.drawables.map(row => [row.path, row]))
  const allCurrent462Census = freeze(poseOracle.inventory.drawables.map(original => {
    const primitive = nativeModel.primitives.get(original.path)
    if (!primitive) throw new Error('Full current source-body census has foreign original drawable ancestry')
    return { path: original.path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, rawNodeIndex: primitive.nodeIndex,
      rawMeshIndex: primitive.meshIndex, rawPrimitiveIndex: primitive.primitiveIndex, instanceOf: primitive.instanceOf,
      bindingOwnerPath: original.bindingOwnerPath, binding: serializeNativeBinding(original.binding), station: original.station }
  }))
  const featureMarkers = freeze(intro.map(row => ({ id: row.witness.anchorId, partPath: row.witness.partPath,
    partLocalMetres: [...row.feature.localPointMetres], sourceFeatureEvidenceSHA256: row.witness.sourceFeatureEvidenceSHA256,
    sourceVideoId: row.sourceBinding.videoId, timeSeconds: 27, viewId: 'main' })))
  return {
    featureMarkers,
    forView({ record, frame, view, binding, viewport }) {
      if (!point(viewport, 2) || viewport.some(n => !Number.isSafeInteger(n) || n < 1)) throw new Error('Actual native viewport dimensions required')
      const originals = originalFrames(record, frame), tuple = sourceTuple(record, frame, view, binding)
      const anchors = new Map((record.observations?.anchors ?? []).map(anchor => [anchor.id, anchor]))
      const projectFeature = createFeatureProjector(binding, viewport)
      const posed = poseOracle.solve(binding.input, binding.partOverrides), posedByPath = new Map(posed.drawables.map(row => [row.path, row]))
      const witnesses = [], sourceFeatures = [], featureSupports = [], rays = [], contours = [], sourceAnchors = [], unavailable = []
      const sourceVisibility = nativeSourceVisibilityExpectation({ record, frame, view, binding })
      const declarations = (frame.landmarks ?? []).filter(row => (row.viewId ?? 'main') === view.id)
      for (const declaration of declarations) {
        const anchorId = declaration.anchorId, context = { viewId: view.id, originalViewId: declaration.originalViewId ?? view.id,
          anchorId, role: declaration.role ?? null, originalRole: declaration.role ?? null, sourceImage: frame.sourceImage }
        try {
          const matches = originals.flatMap(original => original.landmarks ?? []).filter(row => row.anchorId === anchorId
            && (row.viewId ?? 'main') === context.originalViewId && row.status === 'observed' && point(row.pixel, 2)
            && ['fit', 'check'].includes(row.role) && row.role === declaration.role && same(row.pixel, declaration.pixel))
          if (!matches.length || matches.some(row => !same(row, matches[0]))) throw new Error('Exact original source landmark/role is absent or contradictory')
          const original = matches[0], anchor = anchors.get(anchorId), head = introByAnchor.get(anchorId)
          let witness, geometryEvidence, geometryEvidenceSHA256, evidence
          if (head && record.id === head.sourceBinding.videoId && record.native.observedSha256 === head.sourceBinding.sourceSHA256
            && frame.sourceImage.frameIndex === head.sourceBinding.frameIndex && frame.sourceImage.sha256Bgr8 === head.sourceBinding.sha256Bgr8) {
            if (original.role !== 'fit') throw new Error('Original silver-head FIT role cannot be promoted to CHECK')
            evidence = head.sourceBinding
            witness = head.witness; geometryEvidence = head.geometryEvidence; geometryEvidenceSHA256 = head.geometryEvidenceSHA256
          } else {
            const issue = nativeAnchorError(anchor, true)
            if (issue) throw new Error(issue)
            const primitive = nativeModel.primitives.get(anchor.partPath), originalNative = originalByPath.get(anchor.partPath)
            if (!primitive || !originalNative) throw new Error('Original feature has no exact authentic drawable ancestry')
            proveOriginalAncestry(anchor.nativeAssociation.proof, primitive, originalNative, nativeModel)
            evidence = { kind: 'original-source-native-feature-binding', originalSourceBinding: { ...tuple, originalViewId: context.originalViewId, originalLandmark: clone(original) },
              originalAnchor: clone(anchor), rawAncestry: { partPath: primitive.path, nodeIndex: primitive.nodeIndex, meshIndex: primitive.meshIndex, primitiveIndex: primitive.primitiveIndex, instanceOf: primitive.instanceOf } }
            witness = nativeWitnessAtOriginalPoint(primitive, anchor.partLocalMetres, anchorId, jsonDigest(evidence))
          }
          const primitive = nativeModel.primitives.get(witness.partPath), feature = verifyNativeMeshFeatureWitness(witness, primitive), pose = posedByPath.get(witness.partPath)
          if (!pose || ![true, 'visible'].includes(pose.effectiveVisibility)) throw new Error('Original native feature is not visible in the independently solved pose')
          const pixel = projectFeature(feature.localPointMetres, pose)
          if (!pixel) throw new Error('Authentic original feature is outside the current independent camera viewport')
          const supportRays = [], rayAnchorIds = [], raySupports = []
          if (geometryEvidence) {
            const groups = new Map()
            const supportPoints = [
              ...geometryEvidence.topCap.surfaceSupportPoints,
              ...geometryEvidence.floorSurfaceSupports.map(({ vertexIndices, ...support }) => ({ ...support, vertexIndex: null })),
            ]
            for (const support of supportPoints) {
              const supportPixel = projectFeature(support.localPointMetres, pose)
              if (!supportPixel) throw new Error('Authentic head-cap support leaves the independently selected camera')
              const key = supportPixel.join('/')
              let group = groups.get(key)
              if (!group) {
                const supportId = `feature-support:${anchorId}:${rayAnchorIds.length}`
                group = { anchorId: supportId, kind: 'head-cap-pixel-support', candidates: [] }
                groups.set(key, group)
                supportRays.push({ anchorId: supportId, pixel: supportPixel }); rayAnchorIds.push(supportId); raySupports.push(group)
              }
              group.candidates.push(support)
            }
          }
          witnesses.push(freeze(witness)); sourceFeatures.push(freeze({ anchorId, evidence })); rays.push({ anchorId, pixel }, ...supportRays)
          sourceAnchors.push({ id: anchorId, role: original.role, pixel: clone(original.pixel), originalSourceBinding: { ...tuple, originalViewId: context.originalViewId } })
          if (geometryEvidence) featureSupports.push({ anchorId, geometryEvidence, geometryEvidenceSHA256, rayAnchorIds, raySupports })
        } catch (error) { unavailable.push({ ...context, status: 'unmeasured-native', reason: error.message }) }
      }
      const associationIndex = nativeBodyAssociationIndex(record.observations?.nativeBodyAssociations)
      for (const item of (frame.contourChecks ?? []).filter(row => row.viewId === view.id)) {
        const check = item.check
        try {
          const sourceViewId = item.originalViewId ?? view.originalViewId ?? view.id
          const candidates = originals.flatMap(original => [
            ...(original.sourceContourChecks ?? []).filter(row => (row.viewId ?? 'main') === sourceViewId),
            ...(original.views ?? []).filter(v => v.id === sourceViewId).flatMap(v => v.sourceContourChecks ?? []),
          ]).filter(row => row.id === check?.id && same(row, check))
          if (!candidates.length || candidates.some(row => !same(row, candidates[0]))) throw new Error('Exact original partial contour/role is absent or contradictory')
          const authentic = candidates[0], body = resolveNativeBodyAssociation(authentic, associationIndex)
          if (body.status !== 'mapped') throw new Error(body.reason ?? 'Original partial contour native body is unavailable')
          if (!nativeModel.primitives.has(authentic.partPath) || !['fit', 'check'].includes(authentic.role) || !authentic.sourceContourPixels?.length) throw new Error('Original partial contour has no authentic drawable/pixel support')
          proveOriginalAncestry(record.observations.nativeBodyAssociations[body.proofRef]?.proof,
            nativeModel.primitives.get(authentic.partPath), originalByPath.get(authentic.partPath), nativeModel)
          const evidence = { kind: 'original-source-partial-contour-binding', originalSourceBinding: { ...tuple, originalViewId: sourceViewId },
            partPath: authentic.partPath, check: clone(authentic), nativeAssociation: clone(body) }
          const rayAnchorIds = [], selected = new Set()
          // Every original edge row participates. Identical backing pixels are
          // counted once; no tiny fixed ray bank implies an all-state certificate.
          for (const sourcePixel of authentic.sourceContourPixels) {
            if (!point(sourcePixel, 2)) throw new Error('Original partial contour contains invalid source pixels')
            const pixel = sourcePixelToNative(sourcePixel, binding, viewport)
            if (!pixel) throw new Error('Original partial contour is outside the current native viewport')
            const key = pixel.join('/')
            if (selected.has(key)) continue
            selected.add(key)
            const anchorId = `contour:${authentic.id}:${rayAnchorIds.length}`
            rays.push({ anchorId, pixel }); rayAnchorIds.push(anchorId)
          }
          contours.push({ id: authentic.id, partPath: authentic.partPath, sourceFeatureEvidenceSHA256: jsonDigest(evidence), evidence, rayAnchorIds })
        } catch (error) { unavailable.push({ viewId: view.id, originalViewId: item.originalViewId ?? view.id, contourId: check?.id ?? null,
          role: check?.role ?? null, originalRole: check?.role ?? null, status: 'unmeasured-contour', reason: error.message }) }
      }
      return freeze({ witnesses, sourceFrame: clone(frame), sourceView: { ...clone(view), anchors: sourceAnchors, mechanicalState: sourceVisibility.sourceMechanicalState },
        bodyProof: { rays, sourceFeatures, featureSupports, contours }, unavailable, ...sourceVisibility,
        sourceOriginalData: record.observations, allCurrent462Census })
    },
  }
}
