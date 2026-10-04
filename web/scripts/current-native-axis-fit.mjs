/** Camera-independent raw-axis feature preparation. No camera, pixels, GPU,
 * old coordinates, machine-input search, or image warp enters this arithmetic.
 * Parent supplies/fixes raw control declarations BEFORE any camera fit; the
 * adapter retains exact original observations and chosen depth ambiguity.
 *
 * axisControls entries: {anchorId, rawNodeIndex, rawPrimitiveIndex,
 * rawPartPath, rawPrimitiveSHA256, axisIndex:0|1|2,
 * sectionCoordinates:[a,b], axisPointCoordinate:number|'minimum'|'maximum',
 * sourceSemanticEvidence:string, sourceRasterImageSHA256:string}.
 * Source semantics require original description + actual original raster +
 * released current raw assembly identity; a retired association/name alone is
 * not authority. These constructed centres are never opaque surface points.
 */
import { CURRENT_NATIVE_RAW_SHA256, canonicalJson, jsonDigest } from './native-model-byte-proof.mjs'
import { nativeAxisSections, nativeSectionCircle, verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'

const clone = value => JSON.parse(canonicalJson(value))
const fail = message => { throw new Error(`Current raw axis feature: ${message}`) }
const controlKeys = ['anchorId', 'rawNodeIndex', 'rawPrimitiveIndex', 'rawPartPath', 'rawPrimitiveSHA256', 'axisIndex',
  'sectionCoordinates', 'axisPointCoordinate', 'sourceSemanticEvidence', 'sourceRasterImageSHA256']

function outerCycle(section) {
  if (!section.cycles.length) fail('declared open raw plane has no closed contour')
  const circles = section.cycles.map(cycle => ({ cycle, circle: nativeSectionCircle(cycle) }))
  circles.sort((a, b) => b.circle.radiusMetres - a.circle.radiusMetres)
  if (circles.length > 1 && circles[0].circle.radiusMetres === circles[1].circle.radiusMetres) fail('raw outer axis contour is ambiguous; independently freeze exact support instead')
  return circles[0]
}

/** Freeze one geometric axis from two complete actual raw loops. Cartesian
 * plane coordinates are in the primitive's original coordinate basis. */
export function prepareCurrentRawAxisWitness(primitive, control, anchorId, sourceFeatureEvidenceSHA256) {
  if (!primitive || ![0, 1, 2].includes(control.axisIndex) || !Array.isArray(control.sectionCoordinates)
      || control.sectionCoordinates.length !== 2 || !control.sectionCoordinates.every(Number.isFinite)
      || control.sectionCoordinates[0] === control.sectionCoordinates[1]) fail('two distinct finite native-axis planes required')
  let minimum = Infinity, maximum = -Infinity
  for (let i = control.axisIndex; i < primitive.positions.length; i += 3) {
    minimum = Math.min(minimum, primitive.positions[i]); maximum = Math.max(maximum, primitive.positions[i])
  }
  const coordinate = control.axisPointCoordinate === 'minimum' ? minimum : control.axisPointCoordinate === 'maximum' ? maximum : control.axisPointCoordinate
  if (!Number.isFinite(coordinate) || coordinate < minimum || coordinate > maximum) fail('axis point must belong to the actual protected raw axial extent')
  const selected = control.sectionCoordinates.map(value => outerCycle(nativeAxisSections(primitive, control.axisIndex, value)))
  const tangentAxes = [0, 1, 2].filter(axis => axis !== control.axisIndex)
  const centreSeparation = Math.hypot(...tangentAxes.map(axis => selected[0].circle.centreLocalMetres[axis] - selected[1].circle.centreLocalMetres[axis]))
  if (centreSeparation > 1e-7) fail('declared native-axis sections are not coaxial within the unchanged 1e-7m position bound')
  const planes = control.sectionCoordinates.map(value => {
    const plane = [0, 0, 0, -value]; plane[control.axisIndex] = 1; return plane
  })
  const witness = { anchorId, partPath: primitive.path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, sourceFeatureEvidenceSHA256,
    kind: 'geometric-axis', rimTriangleIndices: [...new Set(selected.flatMap(row => row.cycle.triangleIndices))].sort((a, b) => a - b),
    sectionPlaneLocal: planes[0], secondSectionPlaneLocal: planes[1], construction: 'axis-from-two-native-sections-v1', axisPointCoordinate: coordinate }
  const feature = verifyNativeMeshFeatureWitness(witness, primitive)
  return { witness, feature, geometry: { rawAxialExtentMetres: [minimum, maximum], axisIndex: control.axisIndex,
    axisPointCoordinate: coordinate, centreSeparationMetres: centreSeparation,
    sections: selected.map((row, i) => ({ planeLocal: planes[i], circle: row.circle, completeRawTriangleIndices: row.cycle.triangleIndices,
      actualRawEdgeIntersections: row.cycle.endpoints })),
    selection: 'Largest-radius complete closed raw contour at each independently declared plane; no camera/residual/source-pixel selection.',
    pointIsSurfacePoint: false, qualification: 'Geometric axis/centre only, not opaque raw triangle or source first-surface/body eligibility.' } }
}

export function createCurrentNativeAxisFitDefinitions({ nativeModel, originalObservations, source, controls }) {
  if (nativeModel?.rawSHA256 !== CURRENT_NATIVE_RAW_SHA256 || !(nativeModel.primitives instanceof Map) || !Array.isArray(controls)) fail('protected actual current raw model and independently authored controls required')
  const anchors = new Map((originalObservations.anchors ?? []).map(anchor => [anchor.id, anchor])), selectedIds = new Set()
  return controls.map(control => {
    const id = control?.anchorId, originalLandmark = source.landmarks.find(l => l.anchorId === id), originalAnchor = anchors.get(id)
    if (!originalLandmark || selectedIds.has(id)) fail('unknown/duplicate original axis control identity')
    selectedIds.add(id)
    const correspondence = { state: 'chosen-unmeasured', evidence: { kind: 'original-source-raster-current-raw-axis-definition',
      originalSourceFeatureDescription: originalAnchor?.description ?? null, declaration: clone(control),
      ambiguity: 'Original centre pixel/role/uncertainty is immutable. Current geometric axis and selected axial depth are camera-independent choices; source depth, current camera, input recovery, and first-surface/GPU/body acceptance are not established.' } }
    const evidence = { sourceBinding: source.sourceBinding, originalLandmark: clone(originalLandmark), correspondence }
    try {
      if (Object.keys(control).sort().join('\0') !== [...controlKeys].sort().join('\0')
          || !Number.isSafeInteger(control.rawNodeIndex) || control.rawNodeIndex < 0
          || !Number.isSafeInteger(control.rawPrimitiveIndex) || control.rawPrimitiveIndex < 0
          || typeof control.sourceSemanticEvidence !== 'string' || !control.sourceSemanticEvidence.trim()
          || !originalAnchor?.description) fail('closed raw-axis declaration and independent physical source-semantic evidence required')
      const image = source.sourceBinding.sourceImage, sourceHash = image[image.pixelFormat === 'gray8' ? 'sha256Gray8' : 'sha256Bgr8']
      if (control.sourceRasterImageSHA256 !== sourceHash) fail('physical feature declaration does not bind the exact original source raster')
      const primitives = [...nativeModel.primitives.values()].filter(p => p.nodeIndex === control.rawNodeIndex && p.primitiveIndex === control.rawPrimitiveIndex
        && p.rawPath === control.rawPartPath && p.rawPrimitiveSHA256 === control.rawPrimitiveSHA256 && p.instanceOf === null)
      if (primitives.length !== 1) fail('exact independently selected raw node/primitive/body/hash is absent or ambiguous; no name fallback')
      const prepared = prepareCurrentRawAxisWitness(primitives[0], control, id, jsonDigest(evidence))
      return { ...evidence, witness: prepared.witness, rawAxisGeometry: prepared.geometry }
    } catch (error) { return { ...evidence, witness: null, unavailableReason: error.message } }
  })
}
