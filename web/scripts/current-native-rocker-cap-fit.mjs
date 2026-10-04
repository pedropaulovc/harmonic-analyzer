/** Camera-independent construction of an actual stored rocker-stock cap corner.
 * Original decimal local coordinates are retained by the association identity,
 * never rounded, snapped, or used to select a point. No camera, pose, source
 * pixel, CHECK residual, ideal profile equation, or rendered geometry enters
 * the local construction. Surface support is not source/GPU qualification.
 *
 * rockerCapAnchors entries are closed: {anchorId, primitiveIndex, corner,
 * exterior:'minimum-native-Z',
 * construction:'positive-native-X-terminal-stock-cap-corner-v1',
 * sourceSemanticEvidence}. The parent owns CLI byte admission and world export.
 */
import { CURRENT_NATIVE_RAW_SHA256, canonicalJson, jsonDigest, requireClosed } from './native-model-byte-proof.mjs'
import { verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'
import { reproveCurrentNativeFitAssociationPrimitives } from './current-native-fit-association.mjs'

const clone = value => JSON.parse(canonicalJson(value))
const text = value => typeof value === 'string' && value.trim().length > 0
const fail = message => { throw new Error(`Current raw rocker cap: ${message}`) }
const selectionKeys = ['anchorId', 'primitiveIndex', 'corner', 'exterior', 'construction', 'sourceSemanticEvidence']
const construction = 'positive-native-X-terminal-stock-cap-corner-v1'

function validateSelection(control, anchorId) {
  requireClosed(control, selectionKeys, 'Rocker cap selection')
  if (!text(anchorId) || control.anchorId !== anchorId || !Number.isSafeInteger(control.primitiveIndex) || control.primitiveIndex < 0
      || !['top', 'bottom'].includes(control.corner) || control.exterior !== 'minimum-native-Z'
      || control.construction !== construction || !text(control.sourceSemanticEvidence)) fail('explicit closed cap corner/exterior/construction/source-semantic selection required')
}

function rawPoint(primitive, index) {
  return Array.from(primitive.positions.subarray(index * 3, index * 3 + 3))
}

function planarStockFaces(primitive) {
  if (!(primitive?.positions instanceof Float32Array) || !primitive.positions.length || primitive.positions.length % 3
      || !(primitive.index instanceof Uint32Array) || !primitive.index.length || primitive.index.length % 3) fail('actual indexed Float32 POSITION and complete Uint32 triangle indices required')
  for (const value of primitive.positions) if (!Number.isFinite(value)) fail('raw POSITION contains a nonfinite value')
  const vertexCount = primitive.positions.length / 3, planes = new Map()
  for (const index of primitive.index) if (index >= vertexCount) fail('raw triangle index is out of range')
  for (let offset = 0; offset < primitive.index.length; offset += 3) {
    const indices = [primitive.index[offset], primitive.index[offset + 1], primitive.index[offset + 2]]
    const [a, b, c] = indices.map(index => rawPoint(primitive, index))
    if (a[2] !== b[2] || a[2] !== c[2]) continue
    const twiceArea = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if (!Number.isFinite(twiceArea) || twiceArea === 0) fail('degenerate planar face triangle')
    let plane = planes.get(a[2])
    if (!plane) {
      plane = { nativeZ: a[2], minimumNativeX: Infinity, maximumNativeX: -Infinity, triangleIndices: [], vertexIndices: new Set() }
      planes.set(a[2], plane)
    }
    plane.triangleIndices.push(offset / 3)
    for (const index of indices) {
      plane.vertexIndices.add(index)
      plane.minimumNativeX = Math.min(plane.minimumNativeX, primitive.positions[index * 3])
      plane.maximumNativeX = Math.max(plane.maximumNativeX, primitive.positions[index * 3])
    }
  }
  let maximumSpan = 0
  for (const plane of planes.values()) {
    plane.nativeXSpan = plane.maximumNativeX - plane.minimumNativeX
    maximumSpan = Math.max(maximumSpan, plane.nativeXSpan)
  }
  const exteriorPlanes = [...planes.values()].filter(plane => plane.nativeXSpan === maximumSpan).sort((a, b) => a.nativeZ - b.nativeZ)
  if (!(maximumSpan > 0) || !Number.isFinite(maximumSpan) || exteriorPlanes.length !== 2) fail('exactly two distinct stock exterior planes with equal largest native-X span required')
  return { planes: [...planes.values()].sort((a, b) => a.nativeZ - b.nativeZ), exteriorPlanes }
}

function flatFaceBoundary(primitive, plane) {
  const welded = [], byXYZ = new Map(), byRawIndex = new Map()
  const rawVertexIndices = [...plane.vertexIndices].sort((a, b) => a - b)
  for (const index of rawVertexIndices) {
    const localMetres = rawPoint(primitive, index), key = localMetres.join('/')
    let vertex = byXYZ.get(key)
    if (!vertex) {
      vertex = { weldedVertexIndex: welded.length, localMetres, rawVertexIndices: [] }
      welded.push(vertex); byXYZ.set(key, vertex)
    }
    vertex.rawVertexIndices.push(index); byRawIndex.set(index, vertex.weldedVertexIndex)
  }
  const edges = new Map(), triangles = []
  for (const triangleIndex of plane.triangleIndices) {
    const rawIndices = Array.from(primitive.index.subarray(triangleIndex * 3, triangleIndex * 3 + 3))
    const vertices = rawIndices.map(index => byRawIndex.get(index))
    if (new Set(vertices).size !== 3) fail('degenerate exact-welded planar face triangle')
    triangles.push({ triangleIndex, rawVertexIndices: rawIndices, weldedVertexIndices: vertices })
    for (let i = 0; i < 3; i++) {
      const a = Math.min(vertices[i], vertices[(i + 1) % 3]), b = Math.max(vertices[i], vertices[(i + 1) % 3]), key = `${a}/${b}`
      let edge = edges.get(key)
      if (!edge) { edge = { weldedVertexIndices: [a, b], triangleIndices: [] }; edges.set(key, edge) }
      edge.triangleIndices.push(triangleIndex)
      if (edge.triangleIndices.length > 2) fail('nonmanifold planar face edge has more than two triangles')
    }
  }
  const boundaryEdges = [...edges.values()].filter(edge => edge.triangleIndices.length === 1)
  if (!boundaryEdges.length) fail('flat stock face has no boundary')
  const adjacency = new Map()
  for (const [edgeIndex, edge] of boundaryEdges.entries()) {
    const [a, b] = edge.weldedVertexIndices
    if (welded[a].localMetres.every((value, axis) => value === welded[b].localMetres[axis])) fail('zero-length boundary edge')
    for (const [from, to] of [[a, b], [b, a]]) {
      if (!adjacency.has(from)) adjacency.set(from, [])
      adjacency.get(from).push({ to, edgeIndex })
    }
  }
  for (const neighbors of adjacency.values()) if (neighbors.length !== 2) fail('open or branched planar boundary is not a closed 2-valent loop')
  const loops = [], visited = new Set()
  for (const start of adjacency.keys()) {
    if (visited.has(start)) continue
    const vertices = [], edgeIndices = []
    let current = start, previous = null
    do {
      if (visited.has(current)) fail('ambiguous planar boundary component')
      visited.add(current); vertices.push(current)
      const next = adjacency.get(current).find(neighbor => neighbor.to !== previous)
      if (!next) fail('open planar boundary component')
      edgeIndices.push(next.edgeIndex); previous = current; current = next.to
    } while (current !== start)
    if (vertices.length < 3) fail('degenerate planar boundary loop')
    loops.push({ weldedVertexIndices: vertices, boundaryEdgeIndices: edgeIndices })
  }
  return { rawVertexIndices, weldedVertices: welded, completeIndexedTriangles: triangles,
    geometricEdges: [...edges.values()], boundaryEdges, boundaryLoops: loops }
}

/** Select the actual terminal boundary edge by raw native-X midpoint, then its
 * native-Y endpoint. Exact seam duplicates are one geometric point, not extra
 * observations. The closed witness retains every adjacent triangle of the
 * selected actual stored index; diagnostics also retain physical seam support.
 */
export function prepareCurrentNativeRockerCapWitness(primitive, control, anchorId, sourceFeatureEvidenceSHA256) {
  validateSelection(control, anchorId)
  if (primitive?.primitiveIndex !== control.primitiveIndex) fail('selected raw primitive ordinal does not match the actual primitive')
  const stock = planarStockFaces(primitive), front = stock.exteriorPlanes[0], boundary = flatFaceBoundary(primitive, front)
  let greatestMidpoint = -Infinity, selectedEdges = []
  for (const edge of boundary.boundaryEdges) {
    const [a, b] = edge.weldedVertexIndices.map(index => boundary.weldedVertices[index].localMetres)
    const midpoint = (a[0] + b[0]) / 2
    if (midpoint > greatestMidpoint) { greatestMidpoint = midpoint; selectedEdges = [edge] }
    else if (midpoint === greatestMidpoint) selectedEdges.push(edge)
  }
  if (selectedEdges.length !== 1) fail('terminal boundary edge has tied greatest native-X midpoint')
  const edge = selectedEdges[0], endpoints = edge.weldedVertexIndices.map(index => boundary.weldedVertices[index])
  if (!(greatestMidpoint > 0) || endpoints.some(endpoint => endpoint.localMetres[0] <= 0)) fail('terminal cap edge is not on the positive-native-X stock end')
  if (endpoints[0].localMetres[1] === endpoints[1].localMetres[1]) fail('terminal cap edge top/bottom endpoints have equal native Y')
  const top = endpoints[0].localMetres[1] > endpoints[1].localMetres[1] ? endpoints[0] : endpoints[1]
  const bottom = top === endpoints[0] ? endpoints[1] : endpoints[0]
  const selected = control.corner === 'top' ? top : bottom, vertexIndex = selected.rawVertexIndices[0]
  const adjacentTriangleIndices = [], coincidentRawVertexIndices = []
  for (let index = 0; index < primitive.positions.length / 3; index++) {
    if (selected.localMetres.every((value, axis) => value === primitive.positions[index * 3 + axis])) coincidentRawVertexIndices.push(index)
  }
  const coincident = new Set(coincidentRawVertexIndices), coincidentSupportTriangleIndices = []
  for (let offset = 0; offset < primitive.index.length; offset += 3) {
    const indices = primitive.index.subarray(offset, offset + 3)
    if (indices.includes(vertexIndex)) adjacentTriangleIndices.push(offset / 3)
    if (indices.some(index => coincident.has(index))) coincidentSupportTriangleIndices.push(offset / 3)
  }
  const witness = { anchorId, partPath: primitive.path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, sourceFeatureEvidenceSHA256,
    kind: 'mesh-vertex', vertexIndex, adjacentTriangleIndices }
  const feature = verifyNativeMeshFeatureWitness(witness, primitive)
  const describePlane = plane => ({ nativeZ: plane.nativeZ, nativeXBounds: [plane.minimumNativeX, plane.maximumNativeX],
    nativeXSpan: plane.nativeXSpan, completeRawTriangleIndices: [...plane.triangleIndices], completeRawVertexIndices: [...plane.vertexIndices].sort((a, b) => a - b) })
  return { witness, feature, geometry: {
    construction, planarFaces: stock.planes.map(describePlane), stockExteriorPlanes: stock.exteriorPlanes.map(describePlane),
    frontStockPlane: describePlane(front), frontBoundary: boundary,
    selectedTerminalEdge: { ...edge, nativeXMidpoint: greatestMidpoint, top, bottom },
    selectedCorner: control.corner, localPointMetres: [...feature.localPointMetres],
    coincidentRawVertexIndices, coincidentSupportTriangleIndices,
    pointIsStoredVertex: true, pointIsSurfacePoint: true,
    qualification: 'Actual stored raw surface corner only; source depth/physical correspondence, first-surface, GPU, source-body, whole-video and stage acceptance remain unmeasured.',
  } }
}

function uniqueById(rows, label) {
  const result = new Map()
  for (const row of rows) {
    if (!text(row?.id) || result.has(row.id)) fail(`${label} has an absent or duplicate anchor identity`)
    result.set(row.id, row)
  }
  return result
}

/** Preserve every selected original source landmark and tuple, including role,
 * pixels and uncertainty, even when topology or association is unavailable.
 * A physical source description must explicitly authorize top versus bottom;
 * anchor names and old decimal XYZ do not choose the feature.
 */
export function createCurrentNativeRockerCapFitDefinitions({ nativeModel, poseOracle, originalObservations, currentAnchors, source, selections }) {
  if (!Array.isArray(selections) || !Array.isArray(currentAnchors) || !Array.isArray(originalObservations?.anchors)
      || !Array.isArray(source?.landmarks) || !source.sourceBinding || !Array.isArray(poseOracle?.inventory?.drawables)) fail('explicit selections, original/current anchors, source bindings and independently original CPU inventory required')
  const originals = uniqueById(originalObservations.anchors, 'Original source anchors'), anchors = uniqueById(currentAnchors, 'Current source anchors')
  const inventoryByPath = new Map()
  for (const drawable of poseOracle.inventory.drawables) {
    if (!text(drawable?.path) || inventoryByPath.has(drawable.path)) fail('independently original CPU inventory has ambiguous drawable paths')
    inventoryByPath.set(drawable.path, drawable)
  }
  const selectedIds = new Set()
  return selections.map(selection => {
    const id = selection?.anchorId, landmarks = source.landmarks.filter(landmark => landmark.anchorId === id)
    if (landmarks.length !== 1 || selectedIds.has(id)) fail('unknown/duplicate original cap source landmark identity')
    selectedIds.add(id)
    const originalLandmark = landmarks[0], originalAnchor = originals.get(id), anchor = anchors.get(id)
    const correspondence = { state: 'chosen-unmeasured', evidence: {
      kind: 'current-raw-planar-terminal-cap-corner', originalAnchor: clone(originalAnchor ?? null), currentAnchor: clone(anchor ?? null),
      selection: clone(selection), sourceSemanticEvidence: selection.sourceSemanticEvidence ?? null,
      ambiguity: 'Original source landmark/role/pixels/uncertainty and decimal XYZ identity metadata remain unchanged. The minimum-native-Z stock exterior and physical cap correspondence are explicit unmeasured depth/physical-correspondence choices, not source first-surface, GPU, source-body, whole-video or stage acceptance.',
    } }
    const evidence = { sourceBinding: clone(source.sourceBinding), originalLandmark: clone(originalLandmark), correspondence }
    try {
      validateSelection(selection, id)
      if (source.sourceBinding.videoId !== '4mBuyixt22U' || originalObservations.source?.videoId !== source.sourceBinding.videoId) fail('exact original 4mBuyixt22U source binding required')
      const expectedDescription = `Left distal cap ${selection.corner} physical corner on curved LOWER rocker stock`
      if (originalAnchor?.kind !== 'physical-feature' || originalAnchor.description !== expectedDescription) fail('original physical cap description does not authorize the explicit top/bottom semantic selection; no name or nearest fallback')
      if (nativeModel?.rawSHA256 !== CURRENT_NATIVE_RAW_SHA256 || !(nativeModel.primitives instanceof Map)) fail('protected actual current60a raw model required')
      const primitives = reproveCurrentNativeFitAssociationPrimitives({ nativeModel, inventoryByPath, originalAnchor, anchor, primitiveIndex: selection.primitiveIndex })
      const supported = []
      for (const primitive of primitives) {
        try { supported.push(prepareCurrentNativeRockerCapWitness(primitive, selection, id, jsonDigest(evidence))) }
        catch { /* Unsupported actual primitives do not manufacture a point. */ }
      }
      if (supported.length !== 1) fail('exactly one re-proved current raw primitive with successful terminal-cap surface support required')
      return { ...evidence, witness: supported[0].witness, rawRockerCapGeometry: supported[0].geometry }
    } catch (error) { return { ...evidence, witness: null, unavailableReason: error.message } }
  })
}
