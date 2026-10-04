import { createHash } from 'node:crypto'

// Arithmetic only: no renderer, source fit, camera, historic native certificate or
// producer receipt is an authority for a point or its supporting triangles.
const primitiveTopologies = new WeakMap()
function fail(message) { throw new Error(`Native feature witness: ${message}`) }
function integer(value, label, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) fail(`${label} is not an integer >= ${minimum}`)
  return value
}
function finiteVector(value, count, label) {
  if ((!Array.isArray(value) && !(value instanceof Float64Array)) || value.length !== count || value.some(x => !Number.isFinite(x))) fail(`${label} must contain ${count} finite numbers`)
  return value
}
function closed(value, keys, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join('\0') !== [...keys].sort().join('\0')) fail(`${label} has missing or unknown keys`)
}
function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) deepFreeze(child)
    Object.freeze(value)
  }
  return value
}
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
  if (typeof value === 'number' && !Number.isFinite(value)) fail('canonical value is nonfinite')
  return JSON.stringify(value)
}
function equal(actual, expected, label) {
  if (canonical(actual) !== canonical(expected)) fail(`${label} disagrees with original indexed topology`)
}
export function transformWitnessPoint(matrix, point) {
  finiteVector(matrix, 16, 'independently solved posed matrix')
  finiteVector(point, 3, 'local feature point')
  if (matrix[3] !== 0 || matrix[7] !== 0 || matrix[11] !== 0 || matrix[15] !== 1) fail('posed matrix is not affine')
  return [0, 1, 2].map(row => matrix[row] * point[0] + matrix[4 + row] * point[1] + matrix[8 + row] * point[2] + matrix[12 + row])
}
function topology(primitive) {
  if (primitiveTopologies.has(primitive)) return primitiveTopologies.get(primitive)
  const points = [], identities = new Map(), vertexPositionIds = new Uint32Array(primitive.positions.length / 3)
  // Exact float32-coordinate welding, not proximity welding; duplicated seam
  // indices at one coordinate remain one geometric point, with all raw indices.
  for (let i = 0; i < vertexPositionIds.length; i++) {
    const x = primitive.positions[i * 3], y = primitive.positions[i * 3 + 1], z = primitive.positions[i * 3 + 2], key = `${x},${y},${z}`
    let id = identities.get(key)
    if (id === undefined) { id = points.length; identities.set(key, id); points.push([x, y, z]) }
    vertexPositionIds[i] = id
  }
  const result = { points, vertexPositionIds }
  primitiveTopologies.set(primitive, result)
  return result
}
/** Actual native-axis plane/triangle intersections, in the original raw XYZ
 * coordinates. Canonical raw edge identities avoid proximity welding or proxy
 * rotation. Cartesian axis index: X=0, Y=1, Z=2. */
export function nativeAxisSections(primitive, axisIndex, coordinate) {
  if (![0, 1, 2].includes(axisIndex) || !Number.isFinite(coordinate)) fail('section needs a native Cartesian axis and finite coordinate')
  const { points, vertexPositionIds } = topology(primitive)
  if (points.some(p => p[axisIndex] === coordinate)) fail('section passes through a stored vertex; choose an independently frozen open native-axis gap')
  const edges = new Map(), graph = new Map(), segments = [], indices = primitive.index
  function endpoint(ai, bi, rawA, rawB, triangleIndex) {
    if (ai > bi) { [ai, bi] = [bi, ai]; [rawA, rawB] = [rawB, rawA] }
    const key = `${ai}:${bi}`
    if (!edges.has(key)) {
      const a = points[ai], b = points[bi], t = (coordinate - a[axisIndex]) / (b[axisIndex] - a[axisIndex])
      const localMetres = a.map((value, axis) => axis === axisIndex ? coordinate : value + t * (b[axis] - value))
      edges.set(key, { key, rawPositionIds: [ai, bi], parameterFromFirstVertex: t,
        localMetres, supportingRawEdges: [] })
    }
    edges.get(key).supportingRawEdges.push({ triangleIndex, vertexIndices: [rawA, rawB] })
    return key
  }
  for (let offset = 0; offset < indices.length; offset += 3) {
    const ids = [vertexPositionIds[indices[offset]], vertexPositionIds[indices[offset + 1]], vertexPositionIds[indices[offset + 2]]], hits = []
    for (const [ai, bi] of [[0, 1], [1, 2], [2, 0]]) if ((points[ids[ai]][axisIndex] < coordinate) !== (points[ids[bi]][axisIndex] < coordinate)) hits.push(endpoint(ids[ai], ids[bi], indices[offset + ai], indices[offset + bi], offset / 3))
    if (!hits.length) continue
    if (hits.length !== 2 || hits[0] === hits[1]) fail('native section has a degenerate triangle intersection')
    const segment = { triangleIndex: offset / 3, endpointKeys: hits }
    segments.push(segment)
    for (let j = 0; j < 2; j++) {
      if (!graph.has(hits[j])) graph.set(hits[j], [])
      graph.get(hits[j]).push({ next: hits[1 - j], triangleIndex: segment.triangleIndex })
    }
  }
  const cycles = [], seen = new Set()
  for (const start of [...graph.keys()].sort()) {
    if (seen.has(start)) continue
    const pending = [start], component = new Set()
    while (pending.length) {
      const key = pending.pop()
      if (component.has(key)) continue
      component.add(key)
      for (const { next } of graph.get(key)) pending.push(next)
    }
    for (const key of component) if (graph.get(key).length !== 2) fail('native section is not a closed two-valent loop')
    const ordered = [], triangleIndices = [], visited = new Set()
    let current = start, previous = null
    do {
      if (visited.has(current)) fail('native section repeats an endpoint before closure')
      visited.add(current); seen.add(current); ordered.push(edges.get(current))
      const choices = graph.get(current).filter(edge => edge.next !== previous).sort((a, b) => a.next.localeCompare(b.next) || a.triangleIndex - b.triangleIndex)
      if (!choices.length) fail('native section does not close')
      const step = choices[0]
      triangleIndices.push(step.triangleIndex)
      previous = current; current = step.next
    } while (current !== start)
    if (visited.size !== component.size || ordered.length < 3 || new Set(triangleIndices).size !== triangleIndices.length) fail('native section is not one simple indexed cycle')
    cycles.push({ ...(axisIndex === 1 ? { planeY: coordinate } : { axisIndex, planeCoordinate: coordinate }), endpoints: ordered, triangleIndices: [...triangleIndices].sort((a, b) => a - b) })
  }
  return { ...(axisIndex === 1 ? { planeY: coordinate } : { axisIndex, planeCoordinate: coordinate }), cycles, segmentCount: segments.length }
}
export function nativeHorizontalSections(primitive, planeY) {
  return nativeAxisSections(primitive, 1, planeY)
}
function pointInPolygon(x, z, endpoints, tangentAxes = [0, 2]) {
  let inside = false
  for (let i = 0, j = endpoints.length - 1; i < endpoints.length; j = i++) {
    const a = endpoints[i].localMetres, b = endpoints[j].localMetres
    if ((a[tangentAxes[1]] > z) !== (b[tangentAxes[1]] > z) && x < (b[tangentAxes[0]] - a[tangentAxes[0]]) * (z - a[tangentAxes[1]]) / (b[tangentAxes[1]] - a[tangentAxes[1]]) + a[tangentAxes[0]]) inside = !inside
  }
  return inside
}
function solve3(matrix, vector) {
  const rows = matrix.map((row, i) => [...row, vector[i]])
  for (let col = 0; col < 3; col++) {
    let pivot = col
    for (let row = col + 1; row < 3; row++) if (Math.abs(rows[row][col]) > Math.abs(rows[pivot][col])) pivot = row
    if (rows[pivot][col] === 0) fail('native section has no uniquely determined circle centre')
    ;[rows[col], rows[pivot]] = [rows[pivot], rows[col]]
    const scale = rows[col][col]
    for (let j = col; j < 4; j++) rows[col][j] /= scale
    for (let row = 0; row < 3; row++) if (row !== col) {
      const factor = rows[row][col]
      for (let j = col; j < 4; j++) rows[row][j] -= factor * rows[col][j]
    }
  }
  return rows.map(row => row[3])
}
/** Deterministic least-squares circle, with actual radial residual and complete
 * supporting loop. Residual is reported, never silently called a pixel bound. */
export function nativeSectionCircle(cycle) {
  const ps = cycle.endpoints.map(endpoint => endpoint.localMetres), axisIndex = cycle.axisIndex ?? 1
  const tangentAxes = [0, 1, 2].filter(axis => axis !== axisIndex)
  if (![0, 1, 2].includes(axisIndex) || ps.length < 3) fail('native circle requires one closed native-axis section')
  const meanX = ps.reduce((sum, p) => sum + p[tangentAxes[0]], 0) / ps.length, meanZ = ps.reduce((sum, p) => sum + p[tangentAxes[1]], 0) / ps.length
  const scale = Math.max(...ps.map(p => Math.hypot(p[tangentAxes[0]] - meanX, p[tangentAxes[1]] - meanZ)))
  if (!(scale > 0)) fail('native section has zero radius')
  const matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], vector = [0, 0, 0]
  for (const p of ps) {
    const x = (p[tangentAxes[0]] - meanX) / scale, z = (p[tangentAxes[1]] - meanZ) / scale, row = [x, z, 1], value = -(x * x + z * z)
    for (let i = 0; i < 3; i++) { vector[i] += row[i] * value; for (let j = 0; j < 3; j++) matrix[i][j] += row[i] * row[j] }
  }
  const [a, b, c] = solve3(matrix, vector), centre = [0, 0, 0]
  centre[axisIndex] = cycle.planeCoordinate ?? cycle.planeY
  centre[tangentAxes[0]] = meanX - a * scale / 2
  centre[tangentAxes[1]] = meanZ - b * scale / 2
  const radiusSquared = (a * a + b * b) / 4 - c
  if (!(radiusSquared > 0) || !pointInPolygon(centre[tangentAxes[0]], centre[tangentAxes[1]], cycle.endpoints, tangentAxes)) fail('native section centre is not enclosed by its supporting rim')
  const radius = Math.sqrt(radiusSquared) * scale
  let residual = 0, minRadius = Infinity, maxRadius = 0
  for (const p of ps) {
    const actualRadius = Math.hypot(p[tangentAxes[0]] - centre[tangentAxes[0]], p[tangentAxes[1]] - centre[tangentAxes[1]])
    residual = Math.max(residual, Math.abs(actualRadius - radius)); minRadius = Math.min(minRadius, actualRadius); maxRadius = Math.max(maxRadius, actualRadius)
  }
  return { centreLocalMetres: centre, radiusMetres: radius, radialResidualMetres: residual, radiusBoundsMetres: [minRadius, maxRadius] }
}
/** Enumerate authentic cap/cavity triangles pierced by the native +Y axis. */
export function nativeHeadAxisTriangleHits(primitive) {
  const { positions, index: indices } = primitive, hits = []
  for (let offset = 0; offset < indices.length; offset += 3) {
    const ai = indices[offset] * 3, bi = indices[offset + 1] * 3, ci = indices[offset + 2] * 3
    const ay = positions[ai + 1], by = positions[bi + 1], cy = positions[ci + 1]
    if (Math.max(ay, by, cy) < 0) continue
    const ax = positions[ai], az = positions[ai + 2], bx = positions[bi], bz = positions[bi + 2], cx = positions[ci], cz = positions[ci + 2]
    const denominator = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
    if (denominator === 0) continue
    const u = ((bz - cz) * -cx + (cx - bx) * -cz) / denominator
    const v = ((cz - az) * -cx + (ax - cx) * -cz) / denominator, w = 1 - u - v
    // This is a strict closed triangle, not a camera-hit/near-edge tolerance.
    if (Math.min(u, v, w) >= 0) hits.push({ triangleIndex: offset / 3, vertexIndices: Array.from(indices.subarray(offset, offset + 3)), barycentric: [u, v, w], localMetres: [0, u * ay + v * by + w * cy, 0] })
  }
  return hits.sort((a, b) => b.localMetres[1] - a.localMetres[1] || a.triangleIndex - b.triangleIndex)
}
/** Validate a claimed support against re-decoded raw topology. The expected
 * support is frozen independently by the consumer, never selected by receipt. */
export function verifyFrozenFeatureSupport(candidate, expected) {
  equal(candidate, expected, 'feature/support construction')
  return expected
}

const BASE_WITNESS_KEYS = ['anchorId', 'partPath', 'rawPrimitiveSHA256', 'sourceFeatureEvidenceSHA256', 'kind']
const SHA256 = /^[0-9a-f]{64}$/
function validatePrimitive(primitive) {
  if (!primitive || typeof primitive.path !== 'string' || !SHA256.test(primitive.rawPrimitiveSHA256)
      || !(primitive.positions instanceof Float32Array) || primitive.positions.length % 3
      || !(primitive.index instanceof Uint32Array) || primitive.index.length % 3) fail('primitive must come from the independent original-byte parser')
  const count = primitive.positions.length / 3
  for (const value of primitive.positions) if (!Number.isFinite(value)) fail('raw feature POSITION is nonfinite')
  for (const index of primitive.index) if (index >= count) fail('raw feature index is out of range')
}
function pointAt(primitive, index) {
  integer(index, 'feature vertex index')
  if (index >= primitive.positions.length / 3) fail('feature vertex index is out of range')
  return Array.from(primitive.positions.subarray(index * 3, index * 3 + 3))
}
function triangleVertices(primitive, triangleIndex) {
  integer(triangleIndex, 'feature triangle index')
  if (triangleIndex >= primitive.index.length / 3) fail('feature triangle index is out of range')
  return Array.from(primitive.index.subarray(triangleIndex * 3, triangleIndex * 3 + 3))
}
function adjacentTriangles(primitive, vertexIndices) {
  const selected = new Set(vertexIndices), out = []
  for (let i = 0; i < primitive.index.length; i += 3) if (selected.has(primitive.index[i]) || selected.has(primitive.index[i + 1]) || selected.has(primitive.index[i + 2])) out.push(i / 3)
  return out
}
function exactSortedIndices(values, label) {
  if (!Array.isArray(values) || !values.length) fail(`${label} is empty`)
  for (let i = 0; i < values.length; i++) if (!Number.isSafeInteger(values[i]) || values[i] < 0 || (i && values[i] <= values[i - 1])) fail(`${label} must be strictly sorted distinct indices`)
  return values
}
function sectionAxis(plane) {
  finiteVector(plane, 4, 'section plane')
  const axisIndex = plane.slice(0, 3).findIndex(value => value === 1)
  if (axisIndex < 0 || plane.slice(0, 3).some((value, axis) => value !== (axis === axisIndex ? 1 : 0))) fail('only normalized native Cartesian-axis sections are implemented')
  return { axisIndex, coordinate: -plane[3] }
}
function selectedCycle(primitive, plane, triangleIndices) {
  const { axisIndex, coordinate } = sectionAxis(plane), section = nativeAxisSections(primitive, axisIndex, coordinate)
  const selected = exactSortedIndices(triangleIndices, 'rim triangle indices')
  const matches = section.cycles.filter(cycle => canonical(cycle.triangleIndices) === canonical(selected))
  if (matches.length !== 1) fail('rim triangles do not seal one complete native section cycle')
  return matches[0]
}
function incidentCoplanarTriangleSupport(primitive, triangleIndex, point, trianglePoints) {
  const nativeTopology = topology(primitive), { points, vertexPositionIds } = nativeTopology
  const edge1 = trianglePoints[1].map((value, axis) => value - trianglePoints[0][axis])
  const edge2 = trianglePoints[2].map((value, axis) => value - trianglePoints[0][axis])
  const normal = [edge1[1] * edge2[2] - edge1[2] * edge2[1], edge1[2] * edge2[0] - edge1[0] * edge2[2], edge1[0] * edge2[1] - edge1[1] * edge2[0]]
  const length = Math.hypot(...normal)
  if (!(length > 0)) fail('triangle point has a degenerate native support plane')
  for (let axis = 0; axis < 3; axis++) normal[axis] /= length
  const planeFootprint = Number.EPSILON * 64 * trianglePoints.reduce((sum, p) => sum + Math.abs(p[0]) + Math.abs(p[1]) + Math.abs(p[2]), 0) + Number.MIN_VALUE
  // The unchanged position bound applies only to distance from this triangle's
  // authentic edge. It neither welds nearby positions nor searches other faces.
  const edgeFootprint = 1e-7 + planeFootprint, closeEdges = []
  const offset = triangleIndex * 3
  for (const [first, second] of [[0, 1], [1, 2], [2, 0]]) {
    const a = trianglePoints[first], b = trianglePoints[second]
    const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2], square = dx * dx + dy * dy + dz * dz
    if (!(square > 0)) continue
    const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy + (point[2] - a[2]) * dz) / square))
    if (Math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy, point[2] - a[2] - t * dz) > edgeFootprint) continue
    const ids = [vertexPositionIds[primitive.index[offset + first]], vertexPositionIds[primitive.index[offset + second]]].sort((a, b) => a - b)
    closeEdges.push(`${ids[0]}:${ids[1]}`)
  }
  if (!closeEdges.length) return [triangleIndex]
  if (!nativeTopology.edgeTriangleIndices) {
    const edges = new Map()
    for (let i = 0; i < primitive.index.length; i += 3) for (const [first, second] of [[0, 1], [1, 2], [2, 0]]) {
      const a = vertexPositionIds[primitive.index[i + first]], b = vertexPositionIds[primitive.index[i + second]]
      if (a === b) continue
      const key = a < b ? `${a}:${b}` : `${b}:${a}`
      if (!edges.has(key)) edges.set(key, [])
      edges.get(key).push(i / 3)
    }
    nativeTopology.edgeTriangleIndices = edges
  }
  const support = new Set([triangleIndex])
  for (const key of closeEdges) for (const candidate of nativeTopology.edgeTriangleIndices.get(key) ?? []) {
    if (support.has(candidate)) continue
    const ps = [0, 1, 2].map(corner => points[vertexPositionIds[primitive.index[candidate * 3 + corner]]])
    const candidateFootprint = Number.EPSILON * 64 * ps.reduce((sum, p) => sum + Math.abs(p[0]) + Math.abs(p[1]) + Math.abs(p[2]), 0) + planeFootprint
    if (ps.some(p => Math.abs(normal[0] * (p[0] - trianglePoints[0][0]) + normal[1] * (p[1] - trianglePoints[0][1]) + normal[2] * (p[2] - trianglePoints[0][2])) > candidateFootprint)) continue
    const a = ps[1].map((value, axis) => value - ps[0][axis]), b = ps[2].map((value, axis) => value - ps[0][axis])
    if (!(Math.hypot(a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]) > 0)) continue
    support.add(candidate)
  }
  return [...support].sort((a, b) => a - b)
}

/** Consume an independently frozen witness using the raw-byte parser's exact
 * primitive. This proves construction only, not source visibility, fitted-camera
 * eligibility, rendered first-surface support, or conversion of FIT to CHECK. */
export function verifyNativeMeshFeatureWitness(witness, primitive) {
  validatePrimitive(primitive)
  if (!witness || witness.partPath !== primitive.path || witness.rawPrimitiveSHA256 !== primitive.rawPrimitiveSHA256
      || typeof witness.anchorId !== 'string' || !witness.anchorId || !SHA256.test(witness.sourceFeatureEvidenceSHA256)) fail('witness source/primitive seal is inconsistent')
  if (witness.kind === 'mesh-vertex' || witness.kind === 'native-nib-apex') {
    const nib = witness.kind === 'native-nib-apex'
    closed(witness, [...BASE_WITNESS_KEYS, nib ? 'apexVertexIndices' : 'vertexIndex', 'adjacentTriangleIndices'], 'vertex witness')
    const vertices = nib ? exactSortedIndices(witness.apexVertexIndices, 'apex vertex indices') : [witness.vertexIndex]
    const point = pointAt(primitive, vertices[0])
    for (const index of vertices) equal(pointAt(primitive, index), point, 'coincident apex point')
    if (nib) {
      const allCoincident = []
      for (let i = 0; i < primitive.positions.length / 3; i++) if (canonical(pointAt(primitive, i)) === canonical(point)) allCoincident.push(i)
      equal(vertices, allCoincident, 'complete coincident apex raw-index membership')
    }
    const triangles = adjacentTriangles(primitive, vertices)
    if (!triangles.length) fail('feature has no authentic adjacent triangle')
    equal(exactSortedIndices(witness.adjacentTriangleIndices, 'adjacent triangle indices'), triangles, 'complete adjacent triangle membership')
    return { localPointMetres: point, supportTriangleIndices: triangles, supportPointsLocalMetres: [point],
      constructionResidualMetres: 0, localizationRadiusMetres: 0, pointIsStoredVertex: true, pointIsSurfacePoint: true }
  }
  if (witness.kind === 'triangle-point') {
    closed(witness, [...BASE_WITNESS_KEYS, 'triangleIndex', 'barycentric'], 'triangle witness')
    const vertices = triangleVertices(primitive, witness.triangleIndex), weights = finiteVector(witness.barycentric, 3, 'barycentric point')
    if (weights.some(value => value < 0 || value > 1) || weights[0] + weights[1] + weights[2] !== 1) fail('barycentric point is outside its authentic triangle')
    const points = vertices.map(index => pointAt(primitive, index)), point = [0, 1, 2].map(j => points[0][j] + weights[1] * (points[1][j] - points[0][j]) + weights[2] * (points[2][j] - points[0][j]))
    return { localPointMetres: point, supportTriangleIndices: incidentCoplanarTriangleSupport(primitive, witness.triangleIndex, point, points), supportPointsLocalMetres: [point],
      constructionResidualMetres: 0, localizationRadiusMetres: 0, pointIsStoredVertex: points.some(p => canonical(p) === canonical(point)), pointIsSurfacePoint: true }
  }
  if (witness.kind === 'section-center') {
    closed(witness, [...BASE_WITNESS_KEYS, 'rimTriangleIndices', 'sectionPlaneLocal', 'construction', 'secondSectionPlaneLocal'], 'section witness')
    if (witness.construction !== 'circle-center-from-native-section-v1' || witness.secondSectionPlaneLocal !== null) fail('section witness construction is unsupported')
    const cycle = selectedCycle(primitive, witness.sectionPlaneLocal, witness.rimTriangleIndices), circle = nativeSectionCircle(cycle)
    return { localPointMetres: circle.centreLocalMetres, supportTriangleIndices: cycle.triangleIndices,
      supportPointsLocalMetres: cycle.endpoints.map(endpoint => endpoint.localMetres),
      constructionResidualMetres: circle.radialResidualMetres, localizationRadiusMetres: circle.radiusBoundsMetres[1],
      pointIsStoredVertex: false, pointIsSurfacePoint: false }
  }
  if (witness.kind === 'geometric-axis') {
    const hasAxisPoint = Object.hasOwn(witness, 'axisPointCoordinate')
    closed(witness, [...BASE_WITNESS_KEYS, 'rimTriangleIndices', 'sectionPlaneLocal', 'construction', 'secondSectionPlaneLocal', ...(hasAxisPoint ? ['axisPointCoordinate'] : [])], 'axis witness')
    if (witness.construction !== 'axis-from-two-native-sections-v1') fail('axis witness construction is unsupported')
    const planes = [sectionAxis(witness.sectionPlaneLocal), sectionAxis(witness.secondSectionPlaneLocal)]
    if (planes[0].axisIndex !== planes[1].axisIndex || planes[0].coordinate === planes[1].coordinate) fail('axis needs distinct parallel native-axis sections')
    const axisIndex = planes[0].axisIndex
    const sections = planes.map(plane => nativeAxisSections(primitive, axisIndex, plane.coordinate))
    const selected = new Set(exactSortedIndices(witness.rimTriangleIndices, 'two-section rim triangle indices'))
    const cycles = sections.map(section => {
      const matches = section.cycles.filter(cycle => cycle.triangleIndices.every(index => selected.has(index)))
      if (matches.length !== 1) fail('axis support does not determine exactly one complete cycle at each section')
      return matches[0]
    })
    const triangles = [...new Set(cycles.flatMap(cycle => cycle.triangleIndices))].sort((a, b) => a - b)
    equal(witness.rimTriangleIndices, triangles, 'complete two-section support triangle membership')
    const circles = cycles.map(nativeSectionCircle)
    let localPoint = circles[0].centreLocalMetres
    if (hasAxisPoint) {
      if (!Number.isFinite(witness.axisPointCoordinate)) fail('axis point coordinate is nonfinite')
      let minimum = Infinity, maximum = -Infinity
      for (let index = axisIndex; index < primitive.positions.length; index += 3) {
        minimum = Math.min(minimum, primitive.positions[index]); maximum = Math.max(maximum, primitive.positions[index])
      }
      if (witness.axisPointCoordinate < minimum || witness.axisPointCoordinate > maximum) fail('axis point leaves its actual raw axial extent')
      const fraction = (witness.axisPointCoordinate - planes[0].coordinate) / (planes[1].coordinate - planes[0].coordinate)
      localPoint = circles[0].centreLocalMetres.map((value, axis) => axis === axisIndex ? witness.axisPointCoordinate
        : value + fraction * (circles[1].centreLocalMetres[axis] - value))
    }
    return { localPointMetres: localPoint, axisSecondPointLocalMetres: circles[1].centreLocalMetres,
      supportTriangleIndices: triangles, supportPointsLocalMetres: cycles.flatMap(cycle => cycle.endpoints.map(endpoint => endpoint.localMetres)),
      constructionResidualMetres: Math.max(...circles.map(circle => circle.radialResidualMetres)),
      localizationRadiusMetres: Math.max(...circles.map(circle => circle.radiusBoundsMetres[1])),
      pointIsStoredVertex: false, pointIsSurfacePoint: false }
  }
  fail('unsupported closed native feature witness kind')
}

const INTRO_SOURCE = {
  videoId: 'NAsM30MAHLg', sourceSHA256: '595b0ec7b1e1a0b3523d72d33f6e0950bd97dda5ab7032bf91c3e5b9fb7d225d',
  frameIndex: 809, decodedTimestampTicks: 809809, timeBase: '1/30000', decodedTimeSeconds: 26.99363333333333,
  width: 1920, height: 1080, sha256Bgr8: '39644b10abe18220e44e2b708c0e3e0ba882c90fb0f5988f80e8a7fcc9997a75',
}
const INTRO_HEADS = [
  { anchorId: 'frame-cross-screw-6', pixel: [783.0021362304688, 110.01241302490234], rawNodeIndex: 300, rawMeshIndex: 282, positionAccessorIndex: 960, indicesAccessorIndex: 959 },
  { anchorId: 'frame-cross-screw-5', pixel: [1138.9964599609375, 112.00497436523438], rawNodeIndex: 299, rawMeshIndex: 281, positionAccessorIndex: 957, indicesAccessorIndex: 956 },
  { anchorId: 'frame-cross-screw-2', pixel: [792.0613403320312, 985.03076171875], rawNodeIndex: 297, rawMeshIndex: 279, positionAccessorIndex: 951, indicesAccessorIndex: 950 },
  { anchorId: 'frame-cross-screw-1', pixel: [1138.9500732421875, 979.997802734375], rawNodeIndex: 284, rawMeshIndex: 266, positionAccessorIndex: 912, indicesAccessorIndex: 911 },
]
const HEAD_POSITION_SHA256 = 'c3683207f680bf98cda070f06d05ed310b78a98a02701206b74836c5022266d8'
const HEAD_INDEX_SHA256 = '3f58b26812b46396edb00261663a0c7b6e5133c5704843e4381cc7ba12b9bf28'
const HEAD_NORMAL_SHA256 = '6edc8e1ef3a50ded88129f35baf9bcb68ff54d9d167464d1936bdf537cb08a0f'
const HEAD_FLOOR_Y = 0.002962084487080574
const HEAD_MAXIMUM_Y = 0.004556158557534218
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const jsonDigest = value => digest(canonical(value))
function typedDigestLE(array) {
  // Hash canonical scalar bytes even on a big-endian host, not JSON floats.
  const hostIsLE = new Uint8Array(new Uint32Array([1]).buffer)[0] === 1
  if (hostIsLE) return digest(Buffer.from(array.buffer, array.byteOffset, array.byteLength))
  const bytes = Buffer.alloc(array.byteLength)
  for (let i = 0; i < array.length; i++) {
    if (array instanceof Float32Array) bytes.writeFloatLE(array[i], i * 4)
    else bytes.writeUInt32LE(array[i], i * 4)
  }
  return digest(bytes)
}
function sourceHeadBinding(sourceInspection, head) {
  for (const [key, expected] of Object.entries(INTRO_SOURCE)) {
    if (key === 'videoId') continue
    const sourceKey = key === 'sourceSHA256' ? 'sourceSha256' : key
    equal(sourceInspection?.[sourceKey], expected, `original source ${sourceKey}`)
  }
  if (sourceInspection.kind !== 'actual-original-decoded-source-raster-inspection' || !Array.isArray(sourceInspection.headCrops) || sourceInspection.headCrops.length !== 4) fail('primary four-FIT source inspection is absent')
  if (new Set(sourceInspection.headCrops.map(row => row.anchorId)).size !== 4) fail('primary source has duplicate head controls')
  const row = sourceInspection.headCrops.find(row => row.anchorId === head.anchorId)
  if (!row) fail('original head FIT control is absent')
  closed(row, ['anchorId', 'role', 'pixel', 'uncertaintyPx'], 'original head source control')
  equal(row, { anchorId: head.anchorId, role: 'fit', pixel: head.pixel, uncertaintyPx: 4 }, 'immutable original head FIT pixel/uncertainty')
  return { ...INTRO_SOURCE, anchorId: head.anchorId, feature: 'centre-of-visible-slotted-head', role: 'fit', pixel: [...head.pixel], uncertaintyPx: 4 }
}
function verifyHeadTypedGeometry(primitive) {
  validatePrimitive(primitive)
  if (primitive.positions.length !== 69366 * 3 || primitive.index.length !== 141138
      || !(primitive.normals instanceof Float32Array) || primitive.normals.length !== primitive.positions.length
      || typedDigestLE(primitive.positions) !== HEAD_POSITION_SHA256 || typedDigestLE(primitive.index) !== HEAD_INDEX_SHA256
      || typedDigestLE(primitive.normals) !== HEAD_NORMAL_SHA256) fail('head primitive accessor/index bytes changed')
}
/** Freeze the complete original upper-cap patch and authentic rim/slot-lip
 * boundary support. This is NOT the lower cylindrical axis section, which can
 * be hidden behind the front wall even when a same-path ID pixel is present.
 * Actual visibility is evaluated later per point/triangle/depth; no rule here
 * demands that every back/occluded boundary point be visible.
 */
export function nativeHeadCapSurfaceSupport(primitive) {
  verifyHeadTypedGeometry(primitive)
  const { positions, normals, index } = primitive, { points, vertexPositionIds } = topology(primitive)
  const capTriangleIndices = [], edgeIncidence = new Map()
  for (let offset = 0; offset < index.length; offset += 3) {
    const vertices = [index[offset], index[offset + 1], index[offset + 2]]
    const [a, b, c] = vertices.map(vertex => vertex * 3)
    const ys = [positions[a + 1], positions[b + 1], positions[c + 1]]
    if (Math.min(...ys) < HEAD_FLOOR_Y || Math.max(...ys) <= HEAD_FLOOR_Y) continue
    const geometricNormalY = (positions[b + 2] - positions[a + 2]) * (positions[c] - positions[a])
      - (positions[b] - positions[a]) * (positions[c + 2] - positions[a + 2])
    const nativeNormalYSum = normals[a + 1] + normals[b + 1] + normals[c + 1]
    if (geometricNormalY === 0 || nativeNormalYSum <= 0) continue
    const triangleIndex = offset / 3
    capTriangleIndices.push(triangleIndex)
    for (const [ai, bi] of [[0, 1], [1, 2], [2, 0]]) {
      let rawA = vertices[ai], rawB = vertices[bi], idA = vertexPositionIds[rawA], idB = vertexPositionIds[rawB]
      if (idA > idB) { [idA, idB] = [idB, idA]; [rawA, rawB] = [rawB, rawA] }
      const key = `${idA}:${idB}`
      if (!edgeIncidence.has(key)) edgeIncidence.set(key, [])
      edgeIncidence.get(key).push({ triangleIndex, vertexIndices: [rawA, rawB], rawPositionIds: [idA, idB] })
    }
  }
  if (!capTriangleIndices.length) fail('actual native head has no authentic upper-cap surface')
  const boundaryEdges = [], boundaryVertices = new Map()
  for (const incidences of edgeIncidence.values()) {
    if (incidences.length > 2) fail('actual upper-cap patch has a nonmanifold indexed edge')
    if (incidences.length !== 1) continue
    const edge = incidences[0]
    boundaryEdges.push({ ...edge, localPointsMetres: edge.vertexIndices.map(vertex => pointAt(primitive, vertex)) })
    for (let j = 0; j < 2; j++) if (!boundaryVertices.has(edge.rawPositionIds[j])) boundaryVertices.set(edge.rawPositionIds[j], edge.vertexIndices[j])
  }
  if (!boundaryEdges.length) fail('actual native cap has no authentic rim/slot-lip boundary')
  const incidentTriangles = new Map([...boundaryVertices.keys()].map(id => [id, []]))
  for (let offset = 0; offset < index.length; offset += 3) {
    const seen = new Set()
    for (let j = 0; j < 3; j++) {
      const id = vertexPositionIds[index[offset + j]]
      if (incidentTriangles.has(id) && !seen.has(id)) { incidentTriangles.get(id).push(offset / 3); seen.add(id) }
    }
  }
  const surfaceSupportPoints = [...boundaryVertices].sort(([a], [b]) => a - b).map(([id, vertexIndex]) => ({
    construction: 'actual-native-cap-boundary-vertex', vertexIndex, triangleIndex: null, barycentric: null,
    localPointMetres: points[id], supportTriangleIndices: incidentTriangles.get(id),
  }))
  // Surface interiors also remain genuine posed triangle points. A visible
  // surface island alone does not certify closed/full boundary localization;
  // consumers retain which boundary and cap members were actually qualified.
  for (const triangleIndex of capTriangleIndices) {
    const vertices = triangleVertices(primitive, triangleIndex), ps = vertices.map(vertex => pointAt(primitive, vertex))
    surfaceSupportPoints.push({ construction: 'actual-native-cap-triangle-centroid', vertexIndex: null,
      triangleIndex, barycentric: [1 / 3, 1 / 3, 1 / 3],
      localPointMetres: [0, 1, 2].map(axis => ps[0][axis] + (ps[1][axis] - ps[0][axis]) / 3 + (ps[2][axis] - ps[0][axis]) / 3),
      supportTriangleIndices: [triangleIndex] })
  }
  return {
    construction: 'complete-actual-indexed-positive-normal-Y-head-cap-patch-v1',
    actualYBoundsMetres: [HEAD_FLOOR_Y, HEAD_MAXIMUM_Y], normalTypedBytesSHA256: HEAD_NORMAL_SHA256,
    capTriangleIndices, boundaryEdges, surfaceSupportPoints,
    qualification: 'Authentic upper cap/rim/slot-lip geometry only. Per-point nearest actual triangle, same-epoch production material/ID depth and source localization determine partial visible support; neither path ID alone nor visibility of an unrelated point qualifies these locations.',
  }
}
/** Independently author current-v39 expectations from original raw bytes and
 * original Intro809 pixels. This does not adopt an old native coordinate, fit a
 * camera, choose a nearest vertex, or turn a FIT control into an independent CHECK.
 *
 * The marker is a genuine triangle point on the open slot's planar floor. The
 * virtual centre at the head's highest envelope is NOT this point and lies above
 * the floor, in the recess/void. The lower closed cylindrical section establishes
 * its head-axis meaning only, never a visible source rim. Independently frozen
 * actual upper cap/rim/slot-lip facets supply per-point first-surface support.
 *
 * `nativeModel` is the independent byte consumer's original-SHA-proven model,
 * including its exact document/accessor tables and primitive map.
 */
export function freezeIntroSilverHeadWitnesses(nativeModel, sourceInspection) {
  const primitives = nativeModel?.primitives
  if (nativeModel?.rawSHA256 !== '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c'
      || !(primitives instanceof Map) || !nativeModel.document) fail('Intro heads require the independently byte-proven original model')
  const output = []
  for (const head of INTRO_HEADS) {
    const partPath = `harmonic-analyzer/frame/${head.anchorId}`, primitive = primitives.get(partPath)
    verifyHeadTypedGeometry(primitive)
    if (primitive.path !== partPath) fail('head path is aliased to a different original instance')
    equal([primitive.nodeIndex, primitive.meshIndex, primitive.primitiveIndex], [head.rawNodeIndex, head.rawMeshIndex, 0], 'actual head primitive ancestry')
    const rawPrimitive = nativeModel.document.meshes?.[head.rawMeshIndex]?.primitives?.[0]
    if (!rawPrimitive || rawPrimitive.attributes.POSITION !== head.positionAccessorIndex || rawPrimitive.indices !== head.indicesAccessorIndex) fail('actual head accessor membership disagrees with original indexed primitive')
    const sourceBinding = sourceHeadBinding(sourceInspection, head), sourceFeatureEvidenceSHA256 = jsonDigest(sourceBinding)
    const hits = nativeHeadAxisTriangleHits(primitive)
    if (!hits.length || hits[0].localMetres[1] !== HEAD_FLOOR_Y || hits[0].triangleIndex !== 38163) fail('native head slot/cap axis contradicts its actual floor centre')
    equal(hits[0].vertexIndices, [58580, 58579, 58581], 'actual floor triangle raw membership')
    const { points } = topology(primitive)
    const maximumY = points.reduce((value, point) => Math.max(value, point[1]), -Infinity)
    if (maximumY !== HEAD_MAXIMUM_Y || !(maximumY > HEAD_FLOOR_Y) || points.some(point => point[0] === 0 && point[2] === 0 && point[1] >= 0)) fail('head cap/axis topology contradicts its non-vertex slot-floor centre')
    const sectionY = HEAD_FLOOR_Y / 2, sections = nativeHorizontalSections(primitive, sectionY)
    if (sections.cycles.length !== 1 || sections.cycles[0].endpoints.length !== 128) fail('actual native head rim is not its complete closed 128-edge section')
    const cycle = sections.cycles[0], circle = nativeSectionCircle(cycle)
    const circleCentreAxisErrorMetres = Math.hypot(circle.centreLocalMetres[0], circle.centreLocalMetres[2])
    if (circleCentreAxisErrorMetres > circle.radialResidualMetres) fail('closed head rim circle contradicts its actual native slot-floor axis')
    // The floor projection lies inside this exact closed native rim, independently
    // of a camera. A circle residual is geometry evidence, NOT an approved pixel
    // or numerical-normal acceptance budget.
    if (!pointInPolygon(0, 0, cycle.endpoints)) fail('actual head section does not enclose its native floor-axis point')
    const witness = { anchorId: head.anchorId, partPath, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256,
      sourceFeatureEvidenceSHA256, kind: 'triangle-point', triangleIndex: hits[0].triangleIndex, barycentric: [...hits[0].barycentric] }
    const feature = verifyNativeMeshFeatureWitness(witness, primitive)
    const floorTriangles = [38163, 38164].map(triangleIndex => {
      const vertexIndices = triangleVertices(primitive, triangleIndex), localPointsMetres = vertexIndices.map(index => pointAt(primitive, index))
      if (localPointsMetres.some(point => point[1] !== HEAD_FLOOR_Y)) fail('actual slot-floor supporting facets are not coplanar')
      return { triangleIndex, vertexIndices, localPointsMetres }
    })
    const floorSurfaceSupports = floorTriangles.map(triangle => {
      const ps = triangle.localPointsMetres
      return { construction: 'actual-native-slot-floor-triangle-centroid',
        triangleIndex: triangle.triangleIndex, vertexIndices: triangle.vertexIndices, barycentric: [1 / 3, 1 / 3, 1 / 3],
        localPointMetres: [0, 1, 2].map(axis => ps[0][axis] + (ps[1][axis] - ps[0][axis]) / 3 + (ps[2][axis] - ps[0][axis]) / 3),
        supportTriangleIndices: [triangle.triangleIndex] }
    })
    const topCap = nativeHeadCapSurfaceSupport(primitive)
    const supportTriangleIndices = [...new Set([...floorTriangles.map(triangle => triangle.triangleIndex), ...topCap.capTriangleIndices])].sort((a, b) => a - b)
    const geometryEvidence = {
      construction: 'native-slotted-head-floor-axis-v1',
      rawAncestry: { rawNodeIndex: head.rawNodeIndex, rawMeshIndex: head.rawMeshIndex, rawPrimitiveIndex: 0, partPath },
      positionAccessor: { index: head.positionAccessorIndex, componentType: 5126, type: 'VEC3', count: 69366, typedBytesSHA256: HEAD_POSITION_SHA256 },
      indexAccessor: { index: head.indicesAccessorIndex, componentType: 5125, type: 'SCALAR', count: 141138, typedBytesSHA256: HEAD_INDEX_SHA256 },
      floorTriangles, floorSurfaceSupports, headMaximumYMetres: maximumY, axisFloorYMetres: HEAD_FLOOR_Y,
      sectionPlaneLocal: [0, 1, 0, -sectionY], rimTriangleIndices: cycle.triangleIndices,
      rimEndpoints: cycle.endpoints, sectionCircle: circle, circleCentreAxisErrorMetres,
      axisConstructionTriangleIndices: cycle.triangleIndices, topCap,
      supportTriangleIndices, markerPointIsStoredVertex: false, markerPointIsSurfacePoint: true,
      virtualEnvelopeCentreLocalMetres: [0, maximumY, 0], virtualEnvelopeCentreIsSurfacePoint: false,
    }
    const correspondenceChoice = {
      state: 'chosen-unmeasured', sourceFeature: 'centre-of-visible-slotted-head',
      nativeFeature: 'actual-native-slot-floor-axis-triangle-point',
      excludedAlias: 'virtual-axis-centre-at-maximum-native-head-Y',
      qualification: 'Raw geometry construction only; original FIT pixels do not identify floor depth independently. Current pose/camera and actual production/ID first-surface plus visible rim/slot localization remain separate requirements.',
    }
    output.push({ witness, sourceBinding, correspondenceChoice, geometryEvidence, geometryEvidenceSHA256: jsonDigest(geometryEvidence), feature })
  }
  if (new Set(output.map(row => row.geometryEvidence.rawAncestry.rawNodeIndex)).size !== 4 || new Set(output.map(row => row.witness.partPath)).size !== 4) fail('four source heads are not four distinct actual native instances')
  return deepFreeze(output)
}
/** Compare the producer marker to an independently posed raw witness. A caller
 * may use a stricter bound, never relax the unchanged 1e-7 m native position
 * bound. First-surface/source-localization is separate. No camera enters this API. */
export function verifyPosedNativeFeaturePoint(witness, primitive, independentlySolvedMatrix, markerWorldMetres, positionBoundMetres) {
  finiteVector(markerWorldMetres, 3, 'producer feature marker')
  if (!Number.isFinite(positionBoundMetres) || positionBoundMetres < 0 || positionBoundMetres > 1e-7) fail('native feature position bound must not relax 1e-7 m')
  const feature = verifyNativeMeshFeatureWitness(witness, primitive)
  const point = transformWitnessPoint(independentlySolvedMatrix, feature.localPointMetres)
  const error = Math.hypot(...point.map((value, axis) => value - markerWorldMetres[axis]))
  if (error > positionBoundMetres) fail('posed native feature marker disagrees with original topology')
  return { worldPointMetres: point, errorMetres: error, feature }
}
