import * as THREE from 'three'
import type { MechanismInput } from './mechanics'
import type { CapturedSourceLayoutEntry, ModelProvenance } from './scene'
import { NATIVE_RUNTIME_INSTANCES } from './source-assembly'
import type { SourceAssemblyState } from './source-assembly'

export interface NativeInputSnapshot extends Omit<MechanismInput, 'amplitudes' | 'phases'> {
  amplitudes: number[]
  phases: number[]
}
export interface NativeMaterialSnapshot extends Pick<THREE.Material,
  'uuid' | 'type' | 'name' | 'version' | 'visible' | 'side' | 'shadowSide' | 'opacity' | 'transparent'
  | 'alphaTest' | 'alphaHash' | 'alphaToCoverage' | 'depthTest' | 'depthWrite' | 'depthFunc' | 'colorWrite'
  | 'blending' | 'blendSrc' | 'blendDst' | 'blendEquation' | 'blendSrcAlpha' | 'blendDstAlpha' | 'blendEquationAlpha'
  | 'polygonOffset' | 'polygonOffsetFactor' | 'polygonOffsetUnits'
  | 'stencilWrite' | 'stencilFunc' | 'stencilRef' | 'stencilWriteMask' | 'stencilFuncMask' | 'stencilFail' | 'stencilZFail' | 'stencilZPass'
  | 'clipIntersection' | 'clipShadows'> {
  clippingPlanes: { normal: number[]; constant: number }[] | null
  wireframe: boolean
  color: number[] | null; metalness: number | null; roughness: number | null; displacementScale: number | null; displacementBias: number | null
  textures: Record<string, { uuid: string; version: number; channel: number; matrix: number[] }>
  programCacheKey: string
}
export interface NativePrimitiveSubmission {
  objectUuid: string
  materialUuid: string
  group: { start: number; count: number; materialIndex: number | undefined } | null
}
export type NativeObject = THREE.Mesh | THREE.Line | THREE.Points
export interface NativePrimitiveIdentity {
  /** Canonical native node path + primitive ordinal; never the loader's synthetic child name. */
  canonicalId: string
  nodePath: string
  nativeNodeIndex: number
  representationMeshIndex: number
  primitiveIndex: number
  gltfMode: number
  positionAccessor: number
  indexAccessor: number | null
}
export interface NativeSpringSnapshot {
  kind: 'native-stock-spring'
  stock: 'channel' | 'counter'
  uniforms: { springLength: number; springRestLength: number }
  constants: { radiusM: number; insetM: number; endCorrectionM: number; turns: number }
  /** Complete current native shader hook, not a historical private formula. */
  shaderFunctions: string
  positionExpression: string
  normalExpression: string
  cpuEvaluation: 'float64-existing-native-curve-with-decoded-float32-attributes'
}
export interface NativeSpringEvaluator {
  readonly length: { value: number }
  readonly restLength: { value: number }
  descriptor(): NativeSpringSnapshot
  evaluate(geometry: THREE.BufferGeometry, index: number, position: THREE.Vector3, out: THREE.Vector3): void
}
export interface NativeCaptureModel {
  root: THREE.Object3D
  provenance: ModelProvenance
  identityMapSha256: string
  canonicalModelSha256: string
  semanticSha256: string
  expectedArtifactPrimitiveCount: number
  input: MechanismInput
  revision(): number
  inventoryRevision(): number
  readonly bindingFailures: readonly string[]
  readonly currentOverrideMisses: readonly string[]
  verified(): string | null
  identity(object: NativeObject): NativePrimitiveIdentity
  /** Original live artifact drawable for a genuine native clone; null for artifact objects. */
  runtimeTemplate(object: NativeObject): NativeObject | null
  spring(object: NativeObject): NativeSpringEvaluator | null
}
export interface NativePrimitiveDraw {
  drawRevision: number
  rendererFrame: number
  contextRevision: number
  /** CPU renderer submission returned; no GPU fence or GPU completion is claimed. */
  submittedAtPerformanceMs: number
  viewId: string
  timeSeconds: number | null
  camera: {
    uuid: string; positionMetres: number[]; quaternion: number[]; verticalFovDegrees: number; aspect: number; near: number; far: number
    layersMask: number; viewOffset: THREE.PerspectiveCamera['view']; matrixWorld: number[]; matrixWorldInverse: number[]; projectionMatrix: number[]; projectionMatrixInverse: number[]
  }
  viewportBackingPixels: number[]
  scissorBackingPixels: number[]
  scissorTest: boolean
  renderTarget: { uuid: string; width: number; height: number } | null
  canvas: { width: number; height: number; clientWidth: number; clientHeight: number; devicePixelRatio: number }
  presentation: 'native' | 'horizontal-mirror'
  rectSourcePixels: number[]
  sourceOpacity: number
  imagePlaneWarp: unknown
  sourceAssembly: SourceAssemblyState
  sourceLayout: CapturedSourceLayoutEntry[]
  /** CPU render callbacks from the actual native colour draw, NOT GPU pixel/visibility readback. */
  nativeRenderCallbacks: NativePrimitiveSubmission[]
}
export interface NativePrimitiveBuffers {
  /** Bit-preserving packed copies of the actual decoded POSITION rows; no welding. */
  localPositions: Float32Array
  /** Actual draw topology widened losslessly, or explicit sequential topology for a nonindexed draw. */
  indices: Uint32Array
  /** CPU Float64 geometry, NOT exact GPU vertex positions or a raster/first-surface certificate. */
  worldPositions: Float64Array
  springCoordinate?: Float32Array
  springRestCentre?: Float32Array
  springRestTangent?: Float32Array
}
export interface NativePrimitiveManifest {
  id: string
  identity: NativePrimitiveIdentity
  scope: 'artifact' | 'runtime-clone'
  runtimeInstance: { instancePath: string; sourcePartPath: string } | null
  objectUuid: string
  objectName: string
  geometryUuid: string
  vertexCount: number
  indexCount: number
  indexOrigin: 'decoded-index-attribute' | 'nonindexed-sequential'
  decodedPosition: { componentType: 'Float32'; itemSize: 3; normalized: false; interleaved: boolean; version: number }
  decodedIndex: { componentType: string; version: number } | null
  matrixLocal: number[]
  matrixWorld: number[]
  /** All ancestors through the actual scene; hidden artifact geometry is still captured. */
  ancestors: { uuid: string; name: string; visible: boolean; layersMask: number; matrixLocal: number[]; matrixWorld: number[] }[]
  visibility: 'visible-through-ancestors' | 'hidden-by-self' | 'hidden-by-ancestor'
  cameraLayerEligible: boolean
  /** Eligibility is not a GPU visibility/occlusion finding. */
  renderedPresence: 'excluded-by-visibility' | 'excluded-by-camera-layer' | 'excluded-by-material' | 'excluded-by-draw-range' | 'native-render-callback-observed' | 'not-submitted-by-native-renderer'
  renderSubmissions: NativePrimitiveSubmission[]
  drawMode: 'triangles' | 'lines' | 'line-strip' | 'line-loop' | 'points' | 'wireframe-triangles'
  drawRange: { start: number; count: number | null; effectiveStart: number; effectiveCount: number }
  groups: { start: number; count: number; materialIndex: number | undefined }[]
  layersMask: number
  frustumCulled: boolean
  renderOrder: number
  materials: NativeMaterialSnapshot[]
  deformation: NativeSpringSnapshot | { kind: 'matrix-only'; cpuEvaluation: 'float64-matrix-world-on-decoded-float32-position' }
  buffers: { localPositions: string; indices: string; worldPositions: string; springCoordinate?: string; springRestCentre?: string; springRestTangent?: string }
}
export interface NativeRuntimeInstanceBindingManifest {
  partPath: string
  templatePartPath: string
  localGeometryBinding: 'shared-decoded-native-template-attributes-and-index'
  templatePrimitiveIds: string[]
  instancePrimitiveIds: string[]
  templatePrimitiveCount: number
  instancePrimitiveCount: number
  geometryBindingVerified: true
}
export interface NativePrimitiveCensus {
  artifactPrimitiveCount: number
  artifactMeshNodeCount: number
  runtimeClonePrimitiveCount: number
  springPrimitiveCount: number
  artifactSpringPrimitiveCount: number
  runtimeCloneSpringPrimitiveCount: number
}
export interface NativePrimitiveModelSnapshot {
  runtimeRootUuid: string
  provenance: ModelProvenance
  identityMapSha256: string
  canonicalModelSha256: string
  semanticSha256: string
}
interface NativePrimitiveSubmissionMetadataQualification {
  method: 'current-native-renderer-submission-metadata'
  sourceProof: false
  sourceAcceptance: false
  sourceQualification: 'not-performed'
  gpuSafety: 'independent-gpu-rounding-raster-and-first-surface-proof-required'
}
export type NativePrimitiveSubmissionMetadata = NativePrimitiveSubmissionMetadataQualification & ({
  status: 'current-diagnostic-submission'
  reason: null
  model: NativePrimitiveModelSnapshot
  machineRevision: number
  inventoryRevision: number
  input: NativeInputSnapshot
  draw: NativePrimitiveDraw
  census: NativePrimitiveCensus
  runtimeInstanceDeclarations: NativeRuntimeInstanceBindingManifest[]
} | {
  status: 'unavailable' | 'stale'
  reason: string
  model: null
  machineRevision: null
  inventoryRevision: null
  input: null
  draw: null
  census: null
  runtimeInstanceDeclarations: null
})
export type NativePrimitiveSnapshot = {
  status: 'unavailable' | 'stale'
  method: 'current-native-cpu-geometry'
  reason: string
  manifest: null
  buffers: null
} | {
  status: 'captured'
  method: 'current-native-cpu-geometry'
  manifest: {
    schemaVersion: 1
    method: 'current-native-cpu-geometry'
    sourceQualification: 'not-performed'
    gpuSafety: 'independent-gpu-rounding-raster-and-first-surface-proof-required'
    worldCoordinatePrecision: 'float64-cpu-not-exact-gpu'
    geometricResidualToleranceMetres: 1e-7
    geometricResidualStatus: 'not-measured'
    cpuVsGpuRoundingBoundMetres: null
    bufferEncoding: 'typed-arrays-packed-xyz-no-welding'
    bufferByteOrder: 'little-endian' | 'big-endian'
    model: NativePrimitiveModelSnapshot
    machineRevision: number
    inventoryRevision: number
    input: NativeInputSnapshot
    draw: NativePrimitiveDraw
    issues: { bindingFailures: string[]; currentOverrideMisses: string[] }
    census: NativePrimitiveCensus
    primitives: NativePrimitiveManifest[]
    runtimeClones: NativePrimitiveManifest[]
    runtimeInstanceDeclarations: NativeRuntimeInstanceBindingManifest[]
    cloneExclusions: { scope: 'artifact-census-only'; reason: string; primitiveIds: string[] }
  }
  /** Keyed by per-primitive IDs, including clone IDs; excluded from the ordinary bridge snapshot. */
  buffers: Record<string, NativePrimitiveBuffers>
}

export function unavailableNativePrimitiveSnapshot(reason: string, status: 'unavailable' | 'stale' = 'unavailable'): NativePrimitiveSnapshot {
  return { status, method: 'current-native-cpu-geometry', reason, manifest: null, buffers: null }
}

export function nativeInputSnapshot(input: MechanismInput): NativeInputSnapshot {
  return { crankTurns: input.crankTurns, amplitudes: Array.from(input.amplitudes), phases: Array.from(input.phases), gearing: input.gearing, magnification: input.magnification, setup: { ...input.setup } }
}
function materialRecord(material: THREE.Material): NativeMaterialSnapshot {
  const standard = material instanceof THREE.MeshStandardMaterial ? material : null
  const textures: Record<string, { uuid: string; version: number; channel: number; matrix: number[] }> = {}
  for (const [key, value] of Object.entries(material)) {
    if (value instanceof THREE.Texture) textures[key] = { uuid: value.uuid, version: value.version, channel: value.channel, matrix: value.matrix.toArray() }
  }
  return {
    uuid: material.uuid, type: material.type, name: material.name, version: material.version, visible: material.visible,
    side: material.side, shadowSide: material.shadowSide, opacity: material.opacity, transparent: material.transparent,
    alphaTest: material.alphaTest, alphaHash: material.alphaHash, alphaToCoverage: material.alphaToCoverage,
    depthTest: material.depthTest, depthWrite: material.depthWrite, depthFunc: material.depthFunc, colorWrite: material.colorWrite,
    blending: material.blending, blendSrc: material.blendSrc, blendDst: material.blendDst, blendEquation: material.blendEquation,
    blendSrcAlpha: material.blendSrcAlpha, blendDstAlpha: material.blendDstAlpha, blendEquationAlpha: material.blendEquationAlpha,
    polygonOffset: material.polygonOffset, polygonOffsetFactor: material.polygonOffsetFactor, polygonOffsetUnits: material.polygonOffsetUnits,
    stencilWrite: material.stencilWrite, stencilFunc: material.stencilFunc, stencilRef: material.stencilRef,
    stencilWriteMask: material.stencilWriteMask, stencilFuncMask: material.stencilFuncMask, stencilFail: material.stencilFail, stencilZFail: material.stencilZFail, stencilZPass: material.stencilZPass,
    clippingPlanes: material.clippingPlanes?.map(plane => ({ normal: plane.normal.toArray(), constant: plane.constant })) ?? null,
    clipIntersection: material.clipIntersection, clipShadows: material.clipShadows,
    wireframe: standard?.wireframe ?? false, color: standard?.color.toArray() ?? null, metalness: standard?.metalness ?? null,
    roughness: standard?.roughness ?? null, displacementScale: standard?.displacementScale ?? null, displacementBias: standard?.displacementBias ?? null,
    textures, programCacheKey: material.customProgramCacheKey(),
  }
}
function version(attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute): number {
  return attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.version : attribute.version
}
function storage(attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute) {
  return attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.array : attribute.array
}
function float32Rows(geometry: THREE.BufferGeometry, name: string, itemSize: number): Float32Array {
  const attribute = geometry.getAttribute(name)
  if (!attribute || attribute.itemSize !== itemSize || attribute.normalized || !(storage(attribute) instanceof Float32Array)) throw new Error(`Native ${name} is not an unnormalized decoded Float32×${itemSize} attribute`)
  const result = new Float32Array(attribute.count * itemSize)
  // Copy underlying components directly, preserving coincident seam rows and signed zero.
  const source = storage(attribute)
  const stride = attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.stride : attribute.itemSize
  const offset = attribute instanceof THREE.InterleavedBufferAttribute ? attribute.offset : 0
  for (let i = 0; i < attribute.count; i++) for (let axis = 0; axis < itemSize; axis++) result[i * itemSize + axis] = source[i * stride + offset + axis]!
  return result
}
function objects(root: THREE.Object3D): NativeObject[] {
  const result: NativeObject[] = []
  const visit = (object: THREE.Object3D) => {
    if (object.userData.landmarkMarker) return
    if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points) result.push(object)
    for (const child of object.children) visit(child)
  }
  visit(root)
  return result
}
function instanceOf(object: THREE.Object3D, root: THREE.Object3D) {
  for (let node: THREE.Object3D | null = object; node && node !== root; node = node.parent) {
    if (typeof node.userData.nativeInstancePath === 'string' && typeof node.userData.nativeInstanceSource === 'string') {
      return { instancePath: node.userData.nativeInstancePath as string, sourcePartPath: node.userData.nativeInstanceSource as string }
    }
  }
  return null
}
function unsupported(object: NativeObject, spring: NativeSpringEvaluator | null) {
  if (object instanceof THREE.SkinnedMesh || object instanceof THREE.InstancedMesh || object instanceof THREE.BatchedMesh) throw new Error('Skinning, instancing or batching cannot be represented by a single native primitive matrix')
  if (Object.keys(object.geometry.morphAttributes).length) throw new Error('Native morph deformation is not supported by this geometry capture')
  for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
    if (!spring && material.onBeforeCompile !== THREE.Material.prototype.onBeforeCompile) throw new Error('An unregistered native material vertex hook cannot be evaluated as matrix-only geometry')
    if (material instanceof THREE.ShaderMaterial || material instanceof THREE.RawShaderMaterial) throw new Error('An unregistered native shader cannot be evaluated as matrix-only geometry')
    if (material instanceof THREE.MeshStandardMaterial && material.displacementMap) throw new Error('Native displacement-map deformation is not evaluated by this capture')
  }
}
function primitiveRecord(model: NativeCaptureModel, object: NativeObject, draw: NativePrimitiveDraw): NativePrimitiveManifest {
  const spring = model.spring(object)
  unsupported(object, spring)
  const identity = model.identity(object)
  const runtimeInstance = instanceOf(object, model.root)
  const id = runtimeInstance ? `${runtimeInstance.instancePath}::${identity.canonicalId}` : identity.canonicalId
  const position = object.geometry.getAttribute('position')
  if (!position) throw new Error(`Native primitive ${id} has no POSITION`)
  if (position.itemSize !== 3 || position.normalized || !(storage(position) instanceof Float32Array)) throw new Error(`Native primitive ${id} POSITION is not an unnormalized decoded Float32×3 attribute`)
  const index = object.geometry.index
  if (index && (index.itemSize !== 1 || index.normalized || !(index.array instanceof Uint8Array || index.array instanceof Uint16Array || index.array instanceof Uint32Array))) throw new Error(`Native primitive ${id} has an unsupported index attribute`)
  const total = index?.count ?? position.count
  const start = Math.max(0, object.geometry.drawRange.start)
  const end = Math.max(start, Math.min(total, start + object.geometry.drawRange.count))
  const ancestors: NativePrimitiveManifest['ancestors'] = []
  for (let node: THREE.Object3D | null = object; node; node = node.parent) ancestors.push({ uuid: node.uuid, name: node.name, visible: node.visible, layersMask: node.layers.mask, matrixLocal: node.matrix.toArray(), matrixWorld: node.matrixWorld.toArray() })
  const materials = (Array.isArray(object.material) ? object.material : [object.material]).map(materialRecord)
  const visibility = !object.visible ? 'hidden-by-self' : ancestors.some(ancestor => !ancestor.visible) ? 'hidden-by-ancestor' : 'visible-through-ancestors'
  const cameraLayerEligible = (object.layers.mask & draw.camera.layersMask) !== 0
  const wireframe = materials.some(material => material.wireframe)
  const renderSubmissions = draw.nativeRenderCallbacks.filter(submission => submission.objectUuid === object.uuid)
  return {
    id, identity, scope: runtimeInstance ? 'runtime-clone' : 'artifact', runtimeInstance,
    objectUuid: object.uuid, objectName: object.name, geometryUuid: object.geometry.uuid,
    vertexCount: position.count, indexCount: total, indexOrigin: index ? 'decoded-index-attribute' : 'nonindexed-sequential',
    decodedPosition: { componentType: 'Float32', itemSize: 3, normalized: false, interleaved: position instanceof THREE.InterleavedBufferAttribute, version: version(position) },
    decodedIndex: index ? { componentType: index.array.constructor.name, version: index.version } : null,
    matrixLocal: object.matrix.toArray(), matrixWorld: object.matrixWorld.toArray(), ancestors, visibility, cameraLayerEligible,
    renderedPresence: visibility !== 'visible-through-ancestors' ? 'excluded-by-visibility' : !cameraLayerEligible ? 'excluded-by-camera-layer'
      : materials.every(material => !material.visible) ? 'excluded-by-material' : end <= start ? 'excluded-by-draw-range'
        : renderSubmissions.length ? 'native-render-callback-observed' : 'not-submitted-by-native-renderer',
    renderSubmissions,
    drawMode: object instanceof THREE.Points ? 'points' : object instanceof THREE.LineLoop ? 'line-loop' : object instanceof THREE.LineSegments ? 'lines' : object instanceof THREE.Line ? 'line-strip' : wireframe ? 'wireframe-triangles' : 'triangles',
    drawRange: { start: object.geometry.drawRange.start, count: Number.isFinite(object.geometry.drawRange.count) ? object.geometry.drawRange.count : null, effectiveStart: start, effectiveCount: end - start },
    groups: object.geometry.groups.map(group => ({ start: group.start, count: group.count, materialIndex: group.materialIndex })), layersMask: object.layers.mask, frustumCulled: object.frustumCulled, renderOrder: object.renderOrder, materials,
    deformation: spring?.descriptor() ?? { kind: 'matrix-only', cpuEvaluation: 'float64-matrix-world-on-decoded-float32-position' },
    buffers: { localPositions: `${id}/localPositions`, indices: `${id}/indices`, worldPositions: `${id}/worldPositions`,
      ...(spring ? { springCoordinate: `${id}/springCoordinate`, springRestCentre: `${id}/springRestCentre`, springRestTangent: `${id}/springRestTangent` } : {}) },
  }
}
interface NativePrimitiveCaptureEntry {
  object: NativeObject
  record: NativePrimitiveManifest
}

function samePrimitiveIdentity(left: NativePrimitiveIdentity, right: NativePrimitiveIdentity): boolean {
  return left.canonicalId === right.canonicalId && left.nodePath === right.nodePath
    && left.nativeNodeIndex === right.nativeNodeIndex && left.representationMeshIndex === right.representationMeshIndex
    && left.primitiveIndex === right.primitiveIndex && left.gltfMode === right.gltfMode
    && left.positionAccessor === right.positionAccessor && left.indexAccessor === right.indexAccessor
}

/** Reference/cardinality preflight belongs only to explicit capture, before vertex-buffer allocation. */
function runtimeInstanceBindingRecords(
  model: NativeCaptureModel,
  entries: NativePrimitiveCaptureEntry[],
  primitives: NativePrimitiveManifest[],
  runtimeClones: NativePrimitiveManifest[],
): NativeRuntimeInstanceBindingManifest[] {
  const declarations = Object.values(NATIVE_RUNTIME_INSTANCES)
  const instanceRoots = new Map<string, THREE.Object3D>()
  const visit = (node: THREE.Object3D) => {
    if (node.userData.landmarkMarker) return
    const instancePath = node.userData.nativeInstancePath
    if (typeof instancePath === 'string') {
      if (typeof node.userData.nativeInstanceSource !== 'string') throw new Error(`Native runtime instance ${instancePath} has no source part path`)
      if (instanceRoots.has(instancePath)) throw new Error(`Duplicate native runtime instance root ${instancePath}`)
      instanceRoots.set(instancePath, node)
      const declaration = declarations.find(row => row.partPath === instancePath)
      if (declaration && node.userData.nativeInstanceSource !== declaration.templatePartPath) {
        throw new Error(`Declared native runtime instance ${instancePath} uses source part ${node.userData.nativeInstanceSource}; expected ${declaration.templatePartPath}`)
      }
    }
    for (const child of node.children) visit(child)
  }
  visit(model.root)
  const artifactRecords = new Map<NativeObject, NativePrimitiveManifest>()
  for (const { object, record } of entries) if (record.scope === 'artifact') artifactRecords.set(object, record)
  for (const { object, record } of entries) {
    const template = model.runtimeTemplate(object)
    if (record.scope === 'artifact') {
      if (template) throw new Error(`Native runtime clone ${record.id} lacks live runtime instance metadata`)
      continue
    }
    if (!template || template === object) throw new Error(`Native runtime primitive ${record.id} has no genuine original template drawable`)
    const templateRecord = artifactRecords.get(template)
    if (!templateRecord) throw new Error(`Native runtime primitive ${record.id} references a template outside the captured artifact geometry`)
    if (!samePrimitiveIdentity(record.identity, templateRecord.identity)) {
      throw new Error(`Native runtime primitive ${record.id} canonical identity differs from template ${templateRecord.id}`)
    }
    const geometry = object.geometry
    if (!(geometry instanceof THREE.BufferGeometry) || geometry !== template.geometry) {
      throw new Error(`Native runtime primitive ${record.id} does not share the actual template BufferGeometry ${templateRecord.id}`)
    }
    const position = geometry.getAttribute('position')
    const templatePosition = template.geometry.getAttribute('position')
    if (!position || !templatePosition || position.itemSize !== 3 || position.normalized || !(storage(position) instanceof Float32Array)) {
      throw new Error(`Native runtime primitive ${record.id} lacks decoded unnormalized Float32×3 template POSITION`)
    }
    if (position !== templatePosition || storage(position) !== storage(templatePosition)) {
      throw new Error(`Native runtime primitive ${record.id} does not share the template POSITION attribute and storage`)
    }
    if (geometry.index !== template.geometry.index || geometry.index?.array !== template.geometry.index?.array) {
      throw new Error(`Native runtime primitive ${record.id} does not share the template index attribute and storage`)
    }
  }
  return declarations.map<NativeRuntimeInstanceBindingManifest>(declaration => {
    const templateRecords = primitives.filter(record => record.identity.nodePath === declaration.templatePartPath
      || record.identity.nodePath.startsWith(`${declaration.templatePartPath}/`))
    const instanceRecords = runtimeClones.filter(record => record.runtimeInstance!.instancePath === declaration.partPath)
    if (!instanceRoots.has(declaration.partPath) || !instanceRecords.length) {
      throw new Error(`Declared native runtime instance ${declaration.partPath} has no captured live primitives`)
    }
    if (!templateRecords.length) throw new Error(`Declared native runtime template subtree ${declaration.templatePartPath} has no captured artifact primitives`)
    for (const record of instanceRecords) {
      if (record.runtimeInstance!.sourcePartPath !== declaration.templatePartPath) {
        throw new Error(`Declared native runtime instance ${declaration.partPath} primitive ${record.id} uses source part ${record.runtimeInstance!.sourcePartPath}; expected ${declaration.templatePartPath}`)
      }
    }
    if (instanceRecords.length !== templateRecords.length) {
      throw new Error(`Declared native runtime instance ${declaration.partPath} has ${instanceRecords.length} primitives; template subtree ${declaration.templatePartPath} has ${templateRecords.length}`)
    }
    const templateCanonicalIds = new Set(templateRecords.map(record => record.identity.canonicalId))
    for (const record of instanceRecords) {
      if (!templateCanonicalIds.has(record.identity.canonicalId)) {
        throw new Error(`Declared native runtime instance ${declaration.partPath} includes ${record.identity.canonicalId} outside template subtree ${declaration.templatePartPath}`)
      }
    }
    return {
      ...declaration,
      templatePrimitiveIds: templateRecords.map(record => record.id),
      instancePrimitiveIds: instanceRecords.map(record => record.id),
      templatePrimitiveCount: templateRecords.length,
      instancePrimitiveCount: instanceRecords.length,
      geometryBindingVerified: true,
    }
  })
}

interface NativePrimitiveCaptureInventory {
  entries: NativePrimitiveCaptureEntry[]
  primitives: NativePrimitiveManifest[]
  runtimeClones: NativePrimitiveManifest[]
  runtimeInstanceDeclarations: NativeRuntimeInstanceBindingManifest[]
  census: NativePrimitiveCensus
}

/** Shared metadata/reference census; never packs attributes or evaluates vertex positions. */
function nativePrimitiveCaptureInventory(model: NativeCaptureModel, draw: NativePrimitiveDraw): NativePrimitiveCaptureInventory {
  const primitives: NativePrimitiveManifest[] = []
  const runtimeClones: NativePrimitiveManifest[] = []
  const entries: NativePrimitiveCaptureEntry[] = []
  const primitiveIds = new Set<string>()
  const meshNodes = new Set<number>()
  let artifactSpringPrimitiveCount = 0
  let runtimeCloneSpringPrimitiveCount = 0
  for (const object of objects(model.root)) {
    const record = primitiveRecord(model, object, draw)
    if (primitiveIds.has(record.id)) throw new Error(`Duplicate native primitive identity ${record.id}`)
    primitiveIds.add(record.id)
    entries.push({ object, record })
    if (record.scope === 'artifact') {
      primitives.push(record)
      meshNodes.add(record.identity.nativeNodeIndex)
      if (record.deformation.kind === 'native-stock-spring') artifactSpringPrimitiveCount++
    } else {
      runtimeClones.push(record)
      if (record.deformation.kind === 'native-stock-spring') runtimeCloneSpringPrimitiveCount++
    }
  }
  if (primitives.length !== model.expectedArtifactPrimitiveCount) throw new Error(`Measured ${primitives.length} artifact primitives; approved decoded representation expects ${model.expectedArtifactPrimitiveCount}`)
  const runtimeInstanceDeclarations = runtimeInstanceBindingRecords(model, entries, primitives, runtimeClones)
  return {
    entries, primitives, runtimeClones, runtimeInstanceDeclarations,
    census: {
      artifactPrimitiveCount: primitives.length, artifactMeshNodeCount: meshNodes.size, runtimeClonePrimitiveCount: runtimeClones.length,
      springPrimitiveCount: artifactSpringPrimitiveCount + runtimeCloneSpringPrimitiveCount, artifactSpringPrimitiveCount, runtimeCloneSpringPrimitiveCount,
    },
  }
}

/** Only verification-enabled machines register; the ordinary frame loop never visits this map. */
export const nativeCaptureModels = new WeakMap<THREE.Object3D, NativeCaptureModel>()
export const nativeRenderSubmissions = new WeakMap<THREE.WebGLRenderer, NativePrimitiveSubmission[]>()
const nativeSubmissionTracked = new WeakSet<NativeObject>()

/** Observe only verification draws; preserve all existing application callbacks. */
export function trackNativePrimitiveSubmissions(root: THREE.Object3D) {
  for (const object of objects(root)) {
    if (nativeSubmissionTracked.has(object)) continue
    const original = object.onAfterRender
    object.onAfterRender = function (renderer, scene, camera, geometry, material, group) {
      original.call(this, renderer, scene, camera, geometry, material, group)
      const submissions = nativeRenderSubmissions.get(renderer)
      // Three r180's declaration says Object3D Group; the renderer actually
      // passes a BufferGeometry draw group (or null), as renderObject shows.
      const drawGroup = group as unknown as THREE.GeometryGroup | null
      if (submissions) submissions.push({ objectUuid: object.uuid, materialUuid: material.uuid,
        group: drawGroup ? { start: drawGroup.start, count: drawGroup.count, materialIndex: drawGroup.materialIndex } : null })
    }
    nativeSubmissionTracked.add(object)
  }
}

const MATERIAL_STATE_KEYS = [
  'version', 'visible', 'side', 'shadowSide', 'opacity', 'transparent', 'alphaTest', 'alphaHash', 'alphaToCoverage',
  'depthTest', 'depthWrite', 'depthFunc', 'colorWrite', 'blending', 'blendSrc', 'blendDst', 'blendEquation',
  'blendSrcAlpha', 'blendDstAlpha', 'blendEquationAlpha', 'polygonOffset', 'polygonOffsetFactor', 'polygonOffsetUnits',
  'stencilWrite', 'stencilFunc', 'stencilRef', 'stencilWriteMask', 'stencilFuncMask', 'stencilFail', 'stencilZFail', 'stencilZPass',
  'clipIntersection', 'clipShadows', 'vertexColors', 'toneMapped',
] as const

export interface NativeDrawStateToken {
  machineRevision: number
  inventoryRevision: number
  matches(): boolean
}
const nativeDrawTokenModels = new WeakMap<NativeDrawStateToken, NativeCaptureModel>()
interface NativeGraphState {
  record(): number
  matches(generation: number): boolean
}
const nativeGraphStates = new WeakMap<NativeCaptureModel, { inventoryRevision: number; graph: NativeGraphState }>()

/**
 * Reusable numeric/reference seal, not a per-frame manifest. It never reads vertex
 * rows, builds ancestor/material records, evaluates springs or stringifies geometry.
 */
export function sealNativeDrawState(model: NativeCaptureModel): NativeDrawStateToken {
  const inventoryRevision = model.inventoryRevision()
  let cached = nativeGraphStates.get(model)
  if (!cached || cached.inventoryRevision !== inventoryRevision) {
    const nodes: THREE.Object3D[] = []
    const visit = (node: THREE.Object3D) => {
      if (node.userData.landmarkMarker) return
      nodes.push(node)
      for (const child of node.children) visit(child)
    }
    visit(model.root)
    for (let ancestor = model.root.parent; ancestor; ancestor = ancestor.parent) nodes.push(ancestor)
    const parents = nodes.map(node => node.parent)
    const childCounts = nodes.map(node => node.children.reduce((count, child) => count + Number(!child.userData.landmarkMarker), 0))
    const drawables = objects(model.root)
    const geometries = drawables.map(object => ({
      object, geometry: object.geometry, index: object.geometry.index, indexStorage: object.geometry.index?.array,
      attributes: Object.entries(object.geometry.attributes).map(([name, attribute]) => ({ name, attribute, storage: storage(attribute) })),
      groups: object.geometry.groups.map(group => group),
      materials: Array.isArray(object.material) ? [...object.material] : [object.material],
      spring: model.spring(object),
    }))
    const materials = [...new Set(geometries.flatMap(entry => entry.materials))].map(material => ({
      material, hook: material.onBeforeCompile, cacheKey: material.customProgramCacheKey,
      textureSlots: Object.entries(material).filter(([name]) => name === 'map' || name.endsWith('Map')),
      textures: Object.entries(material).filter((entry): entry is [string, THREE.Texture] => entry[1] instanceof THREE.Texture),
      clippingPlanes: material.clippingPlanes ? [...material.clippingPlanes] : [],
    }))
    const initial: number[] = []
    let values: Float64Array | null = null
    let cursor = 0
    let writing = true
    let equal = true
    let generation = 0
    const number = (value: number) => {
      if (!values) initial.push(value)
      else if (writing) values[cursor] = value
      else if (!Object.is(values[cursor], value)) equal = false
      cursor++
    }
    const readState = () => {
      cursor = 0
      equal = true
      for (let nodeIndex = 0; nodeIndex < nodes.length; nodeIndex++) {
        const node = nodes[nodeIndex]!
        let childCount = 0
        for (const child of node.children) if (!child.userData.landmarkMarker) childCount++
        if (node.parent !== parents[nodeIndex] || childCount !== childCounts[nodeIndex]) equal = false
        for (let i = 0; i < 16; i++) { number(node.matrix.elements[i]!); number(node.matrixWorld.elements[i]!) }
        number(node.position.x); number(node.position.y); number(node.position.z)
        number(node.quaternion.x); number(node.quaternion.y); number(node.quaternion.z); number(node.quaternion.w)
        number(node.scale.x); number(node.scale.y); number(node.scale.z)
        number(Number(node.visible)); number(node.layers.mask); number(Number(node.matrixAutoUpdate)); number(Number(node.matrixWorldAutoUpdate))
        number(node.renderOrder); number(Number(node.frustumCulled))
        // Deformed springs have renderer-recognized object-local spheres;
        // changing one after a draw changes its culling eligibility.
        const sphere = (node as THREE.Object3D & { boundingSphere?: THREE.Sphere | null }).boundingSphere
        number(Number(sphere !== undefined))
        number(sphere?.center.x ?? NaN); number(sphere?.center.y ?? NaN); number(sphere?.center.z ?? NaN); number(sphere?.radius ?? NaN)
      }
      for (const entry of geometries) {
        const geometry = entry.object.geometry
        let attributeCount = 0
        for (const name in geometry.attributes) if (Object.hasOwn(geometry.attributes, name)) attributeCount++
        if (geometry !== entry.geometry || geometry.index !== entry.index || geometry.index?.array !== entry.indexStorage
          || geometry.groups.length !== entry.groups.length || attributeCount !== entry.attributes.length) equal = false
        number(geometry.drawRange.start); number(geometry.drawRange.count)
        if (entry.index) { number(entry.index.version); number(entry.index.count); number(entry.index.itemSize); number(Number(entry.index.normalized)) }
        for (const { name, attribute, storage: array } of entry.attributes) {
          if (geometry.getAttribute(name) !== attribute || storage(attribute) !== array) equal = false
          number(version(attribute)); number(attribute.count); number(attribute.itemSize); number(Number(attribute.normalized))
          number(attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.stride : attribute.itemSize)
          number(attribute instanceof THREE.InterleavedBufferAttribute ? attribute.offset : 0)
        }
        for (let i = 0; i < entry.groups.length; i++) {
          const group = geometry.groups[i]
          if (group !== entry.groups[i]) equal = false
          number(group?.start ?? NaN); number(group?.count ?? NaN); number(group?.materialIndex ?? NaN)
        }
        const current = entry.object.material
        if (Array.isArray(current) ? current.length !== entry.materials.length : entry.materials.length !== 1) equal = false
        for (let i = 0; i < entry.materials.length; i++) if ((Array.isArray(current) ? current[i] : current) !== entry.materials[i]) equal = false
        if (entry.spring) { number(entry.spring.length.value); number(entry.spring.restLength.value) }
      }
      for (const { material, hook, cacheKey, textureSlots, textures, clippingPlanes } of materials) {
        if (material.onBeforeCompile !== hook || material.customProgramCacheKey !== cacheKey || (material.clippingPlanes?.length ?? 0) !== clippingPlanes.length) equal = false
        for (const key of MATERIAL_STATE_KEYS) number(material[key] === null ? NaN : Number(material[key]))
        if (material instanceof THREE.MeshStandardMaterial) {
          number(Number(material.wireframe)); number(material.color.r); number(material.color.g); number(material.color.b)
          number(material.metalness); number(material.roughness); number(material.displacementScale); number(material.displacementBias)
        }
        for (const [name, value] of textureSlots) if ((material as unknown as Record<string, unknown>)[name] !== value) equal = false
        for (const [name, texture] of textures) {
          if ((material as unknown as Record<string, unknown>)[name] !== texture) equal = false
          number(texture.version); number(texture.channel)
          for (let i = 0; i < 9; i++) number(texture.matrix.elements[i]!)
        }
        for (let i = 0; i < clippingPlanes.length; i++) {
          const plane = material.clippingPlanes?.[i]
          if (plane !== clippingPlanes[i]) equal = false
          number(plane?.normal.x ?? NaN); number(plane?.normal.y ?? NaN); number(plane?.normal.z ?? NaN); number(plane?.constant ?? NaN)
        }
      }
    }
    readState()
    values = new Float64Array(initial)
    initial.length = 0
    cached = { inventoryRevision, graph: {
      record() {
        writing = true
        readState()
        if (!equal) throw new Error('Native geometry/material references changed outside the Machine inventory contract')
        return ++generation
      },
      matches(expectedGeneration) {
        if (expectedGeneration !== generation) return false
        writing = false
        readState()
        return equal
      },
    } }
    nativeGraphStates.set(model, cached)
  }
  const generation = cached.graph.record()
  const machineRevision = model.revision()
  const graph = cached.graph
  const provenance = { ...model.provenance }
  const token: NativeDrawStateToken = { machineRevision, inventoryRevision, matches() {
    if (model.revision() !== machineRevision || model.inventoryRevision() !== inventoryRevision) return false
    for (const key in provenance) {
      const field = key as keyof ModelProvenance
      if (Object.hasOwn(provenance, key) && model.provenance[field] !== provenance[field]) return false
    }
    return graph.matches(generation)
  } }
  nativeDrawTokenModels.set(token, model)
  return token
}

export function captureNativePrimitives(model: NativeCaptureModel, draw: NativePrimitiveDraw, token: NativeDrawStateToken): NativePrimitiveSnapshot {
  try {
    const problem = model.verified()
    if (problem) return unavailableNativePrimitiveSnapshot(problem)
    if (!token.matches()) return unavailableNativePrimitiveSnapshot('Native geometry, input, uniforms, visibility or materials changed after the submitted draw', 'stale')
    const { entries, primitives, runtimeClones, runtimeInstanceDeclarations, census } = nativePrimitiveCaptureInventory(model, draw)
    const buffers: Record<string, NativePrimitiveBuffers> = Object.create(null)
    const point = new THREE.Vector3()
    const deformed = new THREE.Vector3()
    for (const { object, record } of entries) {
      const localPositions = float32Rows(object.geometry, 'position', 3)
      const worldPositions = new Float64Array(localPositions.length)
      const indices = new Uint32Array(record.indexCount)
      const index = object.geometry.index
      for (let i = 0; i < indices.length; i++) {
        const value = index ? index.array[i]! : i
        if (value >= record.vertexCount) throw new Error(`Native primitive ${record.id} index ${value} exceeds its vertex count`)
        indices[i] = value
      }
      const spring = model.spring(object)
      const primitiveBuffers: NativePrimitiveBuffers = { localPositions, indices, worldPositions }
      if (spring) {
        primitiveBuffers.springCoordinate = float32Rows(object.geometry, 'springCoordinate', 2)
        primitiveBuffers.springRestCentre = float32Rows(object.geometry, 'springRestCentre', 3)
        primitiveBuffers.springRestTangent = float32Rows(object.geometry, 'springRestTangent', 3)
        if (primitiveBuffers.springCoordinate.length / 2 !== record.vertexCount || primitiveBuffers.springRestCentre.length !== localPositions.length || primitiveBuffers.springRestTangent.length !== localPositions.length) throw new Error(`Native primitive ${record.id} has incomplete spring attributes`)
      }
      for (let i = 0; i < record.vertexCount; i++) {
        point.fromArray(localPositions, i * 3)
        if (spring) spring.evaluate(object.geometry, i, point, deformed)
        else deformed.copy(point)
        deformed.applyMatrix4(object.matrixWorld)
        if (!Number.isFinite(deformed.x) || !Number.isFinite(deformed.y) || !Number.isFinite(deformed.z)) throw new Error(`Native primitive ${record.id} produced nonfinite CPU geometry`)
        deformed.toArray(worldPositions, i * 3)
      }
      buffers[record.id] = primitiveBuffers
    }
    return { status: 'captured', method: 'current-native-cpu-geometry', manifest: {
      schemaVersion: 1, method: 'current-native-cpu-geometry', sourceQualification: 'not-performed',
      gpuSafety: 'independent-gpu-rounding-raster-and-first-surface-proof-required', worldCoordinatePrecision: 'float64-cpu-not-exact-gpu',
      geometricResidualToleranceMetres: 1e-7, geometricResidualStatus: 'not-measured', cpuVsGpuRoundingBoundMetres: null, bufferEncoding: 'typed-arrays-packed-xyz-no-welding',
      bufferByteOrder: new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 4 ? 'little-endian' : 'big-endian',
      model: { runtimeRootUuid: model.root.uuid, provenance: { ...model.provenance }, identityMapSha256: model.identityMapSha256, canonicalModelSha256: model.canonicalModelSha256, semanticSha256: model.semanticSha256 },
      machineRevision: model.revision(), inventoryRevision: model.inventoryRevision(), input: nativeInputSnapshot(model.input), draw: structuredClone(draw),
      issues: { bindingFailures: [...model.bindingFailures], currentOverrideMisses: [...model.currentOverrideMisses] },
      census,
      primitives, runtimeClones, runtimeInstanceDeclarations,
      cloneExclusions: { scope: 'artifact-census-only', reason: 'Generated native instances are excluded only from artifact bijection; their geometry and draw eligibility remain in runtimeClones and buffers for full rendered occlusion scope', primitiveIds: runtimeClones.map(record => record.id) },
    }, buffers }
  } catch (error) {
    return unavailableNativePrimitiveSnapshot(error instanceof Error ? error.message : String(error))
  }
}

function unavailableNativePrimitiveSubmissionMetadata(
  reason: string,
  status: 'unavailable' | 'stale' = 'unavailable',
): NativePrimitiveSubmissionMetadata {
  return {
    status, method: 'current-native-renderer-submission-metadata', reason,
    sourceProof: false, sourceAcceptance: false, sourceQualification: 'not-performed',
    gpuSafety: 'independent-gpu-rounding-raster-and-first-surface-proof-required',
    model: null, machineRevision: null, inventoryRevision: null, input: null, draw: null, census: null, runtimeInstanceDeclarations: null,
  }
}

/**
 * Explicit scoped diagnostic submission only, not a CPU geometry capture or source
 * acceptance. The Scene adapter owns the diagnostic lease/context/camera guards;
 * model.verified() deliberately remains authoritative for ordinary full capture.
 */
export function diagnosticNativePrimitiveMetadata(
  model: NativeCaptureModel,
  draw: NativePrimitiveDraw,
  token: NativeDrawStateToken,
): NativePrimitiveSubmissionMetadata {
  try {
    if (model.provenance.identity !== 'matched') return unavailableNativePrimitiveSubmissionMetadata('Native model bytes are not identity-matched')
    if (!token.matches()) return unavailableNativePrimitiveSubmissionMetadata('Native state changed after the diagnostic submitted draw', 'stale')
    const ownedDraw = structuredClone(draw)
    const { census, runtimeInstanceDeclarations } = nativePrimitiveCaptureInventory(model, ownedDraw)
    const result: NativePrimitiveSubmissionMetadata = {
      status: 'current-diagnostic-submission', method: 'current-native-renderer-submission-metadata', reason: null,
      sourceProof: false, sourceAcceptance: false, sourceQualification: 'not-performed',
      gpuSafety: 'independent-gpu-rounding-raster-and-first-surface-proof-required',
      model: { runtimeRootUuid: model.root.uuid, provenance: { ...model.provenance }, identityMapSha256: model.identityMapSha256,
        canonicalModelSha256: model.canonicalModelSha256, semanticSha256: model.semanticSha256 },
      machineRevision: model.revision(), inventoryRevision: model.inventoryRevision(),
      input: nativeInputSnapshot(model.input), draw: ownedDraw, census, runtimeInstanceDeclarations,
    }
    if (!token.matches()) return unavailableNativePrimitiveSubmissionMetadata('Native state changed while collecting diagnostic submission metadata', 'stale')
    return result
  } catch (error) {
    return unavailableNativePrimitiveSubmissionMetadata(error instanceof Error ? error.message : String(error))
  }
}

export interface NativeTargetSurfaceRequest {
  expectedDrawRevision: number
  expectedContextRevision: number
  expectedViewId: string
  expectedTimeSeconds: number | null
  targetPrimitiveId: string
  /** Offset in the actual topology, not a vertex number or welded triangle. */
  targetIndexOffset: number
  exactLocalPosition: readonly [number, number, number]
  /** Absolute GL native-stage backing coordinates; Scene checks pixel limits. */
  nativeStageBackingPixel: readonly [number, number]
}

export interface NativeTargetSurfaceId {
  primitiveId: string
  canonicalPrimitiveId: string
  triangleIndexOffset: number | null
}

export interface NativeTargetSurfaceAssociation extends Omit<NativeTargetSurfaceId, 'primitiveId' | 'canonicalPrimitiveId'> {
  primitiveId: string | null
  canonicalPrimitiveId: string | null
  status: 'target-incident-triangle' | 'target-other-triangle' | 'occluded-by-native-primitive' | 'no-native-surface' | 'unresolved'
  requestedTriangleIndexOffset: number
  targetClassVertexIndices: readonly number[]
  incidentTriangleIndexOffsets: readonly number[]
  rawPixel: readonly [number, number, number, number]
  sourceProof: false
  sourceAcceptance: false
  numericVertexResidualBoundMetres: null
  gpuPositionRoundingBoundMetres: null
  eligibility: 'unresolved'
}

export interface NativeTargetSurfaceInspection {
  request: NativeTargetSurfaceRequest
  model: NativePrimitiveModelSnapshot
  machineRevision: number
  inventoryRevision: number
  input: NativeInputSnapshot
  draw: NativePrimitiveDraw
  census: NativePrimitiveCensus
  runtimeInstanceDeclarations: NativeRuntimeInstanceBindingManifest[]
  target: {
    object: NativeObject
    record: NativePrimitiveManifest
    primitiveId: string
    canonicalPrimitiveId: string
    classVertexIndices: readonly number[]
    incidentTriangleIndexOffsets: readonly number[]
    triangleCount: number
  }
}

export interface NativeTargetSurfacePass extends NativeTargetSurfaceInspection {
  method: 'current-native-depth-target-surface-association'
  equivalence: 'depth-native-not-colour-or-composite'
  entries: {
    object: NativeObject
    originalMaterial: THREE.Material | THREE.Material[]
    diagnosticMaterial: THREE.Material | THREE.Material[]
  }[]
  target: NativeTargetSurfaceInspection['target'] & {
    originalGeometry: THREE.BufferGeometry
    diagnosticGeometry: THREE.BufferGeometry
    keyAttributeName: string
  }
  idLookup: ReadonlyMap<number, NativeTargetSurfaceId>
  sourceProof: false
  sourceAcceptance: false
  numericVertexResidualBoundMetres: null
  gpuPositionRoundingBoundMetres: null
  eligibility: 'unresolved'
  decodePixel(pixel: Uint8Array): NativeTargetSurfaceAssociation
  /** Does not restore Scene state or dispose original buffers/materials/textures. */
  dispose(): void
}

const NATIVE_TARGET_TRIANGLE_KEY_ATTRIBUTE = 'nativeTargetTriangleKey'
const NATIVE_TARGET_RGB24_MAX = 0xffffff

function assertNativeTargetRequest(model: NativeCaptureModel, draw: NativePrimitiveDraw, token: NativeDrawStateToken, request: NativeTargetSurfaceRequest) {
  if (nativeCaptureModels.get(model.root) !== model || model.provenance.identity !== 'matched') throw new Error('Target-surface association requires the registered identity-matched native model')
  if (nativeDrawTokenModels.get(token) !== model || token.machineRevision !== model.revision() || token.inventoryRevision !== model.inventoryRevision() || !token.matches()) {
    throw new Error('Native target-surface state is stale or the draw token belongs to a different model')
  }
  if (!Number.isSafeInteger(request.expectedDrawRevision) || !Number.isSafeInteger(request.expectedContextRevision)
    || typeof request.expectedViewId !== 'string' || !request.expectedViewId
    || (request.expectedTimeSeconds !== null && !Number.isFinite(request.expectedTimeSeconds))
    || request.expectedDrawRevision !== draw.drawRevision || request.expectedContextRevision !== draw.contextRevision
    || request.expectedViewId !== draw.viewId || !Object.is(request.expectedTimeSeconds, draw.timeSeconds)) {
    throw new Error('Native target-surface request does not match the completed current draw revision/context/view/time')
  }
  if (typeof request.targetPrimitiveId !== 'string' || !request.targetPrimitiveId
    || !Number.isSafeInteger(request.targetIndexOffset) || request.targetIndexOffset < 0 || request.targetIndexOffset % 3 !== 0) {
    throw new Error('Native target-surface request requires a primitive ID and a nonnegative triangle-aligned index offset')
  }
  if (!Array.isArray(request.exactLocalPosition) || request.exactLocalPosition.length !== 3
    || request.exactLocalPosition.some(value => !Number.isFinite(value) || !Object.is(value, Math.fround(value)))) {
    throw new Error('Native target coordinate must be exactly representable finite Float32, including signed zero')
  }
  if (!Array.isArray(request.nativeStageBackingPixel) || request.nativeStageBackingPixel.length !== 2
    || request.nativeStageBackingPixel.some(value => !Number.isSafeInteger(value))) {
    throw new Error('Native target pixel must contain two integer GL native-stage backing coordinates')
  }
  const projection = draw.camera.projectionMatrix
  if (projection.length !== 16 || projection.some(value => !Number.isFinite(value))
    || projection[0]! <= 0 || projection[5]! <= 0 || projection[11] !== -1 || projection[15] !== 0
    || [1, 2, 3, 4, 6, 7, 12, 13].some(index => projection[index] !== 0)) {
    throw new Error('Native target-surface association supports only the actual native perspective projection')
  }
}

function assertNativeTargetTopology(entry: NativePrimitiveCaptureEntry) {
  const { object, record } = entry
  const geometry = object.geometry
  const total = record.indexCount
  if (!(object instanceof THREE.Mesh) || record.drawMode !== 'triangles' || record.identity.gltfMode !== 4
    || !Number.isSafeInteger(total) || total <= 0 || total % 3 !== 0 || !Number.isSafeInteger(record.vertexCount) || record.vertexCount <= 0) {
    throw new Error(`Native primitive ${record.id} does not have supported complete triangle topology`)
  }
  const alignedRange = (start: number, count: number, label: string, allowInfinity: boolean) => {
    if (!Number.isSafeInteger(start) || start < 0 || start > total || start % 3 !== 0
      || (count !== Infinity || !allowInfinity) && (!Number.isSafeInteger(count) || count < 0 || count % 3 !== 0 || !Number.isSafeInteger(start + count))) {
      throw new Error(`Native primitive ${record.id} has an unsupported ${label}; triangle alignment must be native, not normalized`)
    }
  }
  alignedRange(geometry.drawRange.start, geometry.drawRange.count, 'draw range', true)
  const materials = Array.isArray(object.material) ? object.material : [object.material]
  for (const group of geometry.groups) {
    alignedRange(group.start, group.count, 'material group', false)
    if (Array.isArray(object.material) && (!Number.isSafeInteger(group.materialIndex) || group.materialIndex! < 0 || group.materialIndex! >= materials.length)) {
      throw new Error(`Native primitive ${record.id} has an unresolved material group`)
    }
  }
  for (const material of materials) {
    if (!(material instanceof THREE.MeshStandardMaterial || material instanceof THREE.MeshBasicMaterial
      || material instanceof THREE.MeshLambertMaterial || material instanceof THREE.MeshPhongMaterial || material instanceof THREE.MeshToonMaterial)) {
      throw new Error(`Native primitive ${record.id} has unsupported native material ${material.type}`)
    }
    if (material.wireframe || ('displacementMap' in material && material.displacementMap)) throw new Error(`Native primitive ${record.id} uses wireframe or displacement`)
    if (!Number.isFinite(material.alphaTest) || material.alphaTest < 0) throw new Error(`Native primitive ${record.id} has unsupported native alpha-test semantics`)
    if (material.transparent || material.opacity !== 1 || material.alphaHash || material.alphaToCoverage || material.stencilWrite
      || (material.blending !== THREE.NormalBlending && material.blending !== THREE.NoBlending)) {
      throw new Error(`Native primitive ${record.id} has unsupported nonopaque, stochastic, coverage, stencil or custom blending semantics; this pass is depth-native, not colour-equivalent`)
    }
    if (!material.depthTest || !material.depthWrite) {
      throw new Error(`Native primitive ${record.id} disables native depth testing or depth writing; target association cannot replace its actual depth law`)
    }
  }
  for (const [name, attribute] of Object.entries(geometry.attributes)) {
    const interleaved = attribute instanceof THREE.InterleavedBufferAttribute
    const array = storage(attribute)
    if (attribute instanceof THREE.InstancedBufferAttribute || interleaved && attribute.data instanceof THREE.InstancedInterleavedBuffer
      || !(attribute instanceof THREE.BufferAttribute || interleaved) || !ArrayBuffer.isView(array) || array instanceof DataView
      || !Number.isSafeInteger(attribute.itemSize) || attribute.itemSize < 1 || attribute.itemSize > 4
      || attribute.count !== record.vertexCount || array instanceof Float64Array
      || array.length !== attribute.count * (interleaved ? attribute.data.stride : attribute.itemSize)
      || interleaved && (!Number.isSafeInteger(attribute.data.stride) || !Number.isSafeInteger(attribute.offset)
        || attribute.offset < 0 || attribute.offset + attribute.itemSize > attribute.data.stride)) {
      throw new Error(`Native primitive ${record.id} attribute ${name} has unsupported or mixed vertex topology/storage`)
    }
  }
  if (record.deformation.kind === 'native-stock-spring') {
    for (const [name, size] of [['springCoordinate', 2], ['springRestCentre', 3], ['springRestTangent', 3]] as const) {
      const attribute = geometry.getAttribute(name)
      if (!attribute || attribute.itemSize !== size || attribute.normalized || !(storage(attribute) instanceof Float32Array)
        || attribute.count !== record.vertexCount) throw new Error(`Native spring primitive ${record.id} lacks the actual decoded ${name} attribute law`)
    }
  }
  const index = geometry.index
  if (index && index.array.length !== index.count) throw new Error(`Native primitive ${record.id} index count differs from its actual decoded storage`)
  if (index) for (let offset = 0; offset < total; offset++) {
    if (index.array[offset]! >= record.vertexCount) throw new Error(`Native primitive ${record.id} index at ${offset} exceeds its actual vertex count`)
  }
}

function nativeTargetTriangleActive(entry: NativePrimitiveCaptureEntry, offset: number): boolean {
  const { object, record } = entry
  const materials = object.material
  if (record.renderedPresence !== 'native-render-callback-observed' || offset < record.drawRange.effectiveStart
    || offset + 3 > record.drawRange.effectiveStart + record.drawRange.effectiveCount) return false
  if (!Array.isArray(materials)) return materials.visible
  return object.geometry.groups.some(group => offset >= group.start && offset + 3 <= group.start + group.count
    && materials[group.materialIndex!]?.visible
    && record.renderSubmissions.some(submission => submission.group?.start === group.start
      && submission.group.count === group.count && submission.group.materialIndex === group.materialIndex
      && submission.materialUuid === materials[group.materialIndex!]!.uuid))
}

function nativeTargetDiagnosticMainTail(source: string, statement: string): string {
  const mains = source.match(/\bvoid\s+main\s*\(\s*\)\s*\{/g)
  const end = source.lastIndexOf('}')
  if (mains?.length !== 1 || end < 0 || source.slice(end + 1).trim()) throw new Error('Native diagnostic shader has an unsupported main/output layout')
  return `${source.slice(0, end)}\n${statement}\n${source.slice(end)}`
}

function nativeTargetDiagnosticMaterial(source: THREE.Material, key: number, target: boolean): THREE.Material {
  const result = source.clone()
  const nativeCompile = source.onBeforeCompile
  const nativeCacheKey = source.customProgramCacheKey()
  const colour = target ? null : new THREE.Vector3((key & 255) / 255, ((key >>> 8) & 255) / 255, ((key >>> 16) & 255) / 255)
  result.onBeforeCompile = (shader, renderer) => {
    // The actual native hook supplies the same live spring uniform references.
    nativeCompile.call(source, shader, renderer)
    if (target) {
      shader.vertexShader = `attribute vec3 ${NATIVE_TARGET_TRIANGLE_KEY_ATTRIBUTE};\nvarying vec3 nativeTargetTriangleId;\n${shader.vertexShader}`
      shader.vertexShader = nativeTargetDiagnosticMainTail(shader.vertexShader, `nativeTargetTriangleId = ${NATIVE_TARGET_TRIANGLE_KEY_ATTRIBUTE};`)
      shader.fragmentShader = `varying vec3 nativeTargetTriangleId;\n${shader.fragmentShader}`
    } else {
      shader.uniforms.nativeTargetPrimitiveId = { value: colour }
      shader.fragmentShader = `uniform vec3 nativeTargetPrimitiveId;\n${shader.fragmentShader}`
    }
    // Keep native clipping and alpha-test discards, then overwrite *after* all
    // colour-space/output chunks. No new alpha law or colour qualification.
    shader.fragmentShader = nativeTargetDiagnosticMainTail(shader.fragmentShader,
      `gl_FragColor = vec4(${target ? 'nativeTargetTriangleId' : 'nativeTargetPrimitiveId'}, 1.0);`)
  }
  result.customProgramCacheKey = () => `${nativeCacheKey}:native-target-depth-rgb24:${target ? 'triangle' : 'primitive'}`
  result.depthTest = true
  result.depthWrite = true
  result.colorWrite = true
  result.blending = THREE.NoBlending
  result.dithering = false
  result.toneMapped = false
  // Material.copy clones clipping planes; retain the actual live native refs.
  result.clippingPlanes = source.clippingPlanes
  return result
}

function copyNativeTargetAttributes(original: THREE.BufferGeometry, diagnostic: THREE.BufferGeometry, count: number, primitiveCount: number) {
  const index = original.index
  for (const [name, attribute] of Object.entries(original.attributes)) {
    const source = storage(attribute)
    const ArrayType = source.constructor as THREE.TypedArrayConstructor
    const array = new ArrayType(count * attribute.itemSize)
    const stride = attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.stride : attribute.itemSize
    const offset = attribute instanceof THREE.InterleavedBufferAttribute ? attribute.offset : 0
    for (let row = 0; row < count; row++) {
      const sourceRow = index ? index.array[row]! : row
      for (let axis = 0; axis < attribute.itemSize; axis++) array[row * attribute.itemSize + axis] = source[sourceRow * stride + offset + axis]!
    }
    const copy = attribute instanceof THREE.Float16BufferAttribute
      ? new THREE.Float16BufferAttribute(array as Uint16Array, attribute.itemSize, attribute.normalized)
      : new THREE.BufferAttribute(array, attribute.itemSize, attribute.normalized)
    copy.name = attribute.name
    copy.setUsage(attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.usage : attribute.usage)
    if (attribute instanceof THREE.BufferAttribute) copy.gpuType = attribute.gpuType
    diagnostic.setAttribute(name, copy)
  }
  const keys = new Uint8Array(count * 3)
  for (let offset = 0; offset < count; offset += 3) {
    const key = primitiveCount + 1 + offset / 3
    for (let vertex = 0; vertex < 3; vertex++) {
      const destination = (offset + vertex) * 3
      keys[destination] = key & 255
      keys[destination + 1] = (key >>> 8) & 255
      keys[destination + 2] = (key >>> 16) & 255
    }
  }
  diagnostic.setAttribute(NATIVE_TARGET_TRIANGLE_KEY_ATTRIBUTE, new THREE.BufferAttribute(keys, 3, true))
  diagnostic.name = original.name
  diagnostic.userData = original.userData
  diagnostic.setDrawRange(original.drawRange.start, original.drawRange.count)
  for (const group of original.groups) diagnostic.addGroup(group.start, group.count, group.materialIndex)
  diagnostic.boundingBox = original.boundingBox?.clone() ?? null
  diagnostic.boundingSphere = original.boundingSphere?.clone() ?? null
}

/** Same actual request/inventory/class boundary for metadata and GPU preparation. */
function inspectNativeTargetSurfaceRequest(
  model: NativeCaptureModel,
  draw: NativePrimitiveDraw,
  token: NativeDrawStateToken,
  request: NativeTargetSurfaceRequest,
): { inspection: NativeTargetSurfaceInspection; nativeEntries: NativePrimitiveCaptureEntry[] } {
  assertNativeTargetRequest(model, draw, token, request)
  const inventory = nativePrimitiveCaptureInventory(model, draw)
  const target = inventory.entries.find(entry => entry.record.id === request.targetPrimitiveId)
  if (!target) throw new Error(`Native target primitive ${request.targetPrimitiveId} is not one unique actual artifact/runtime primitive`)
  const original = target.object.geometry
  if (original.hasAttribute(NATIVE_TARGET_TRIANGLE_KEY_ATTRIBUTE)) throw new Error('Native target geometry already contains the reserved diagnostic key attribute')
  const triangleCount = target.record.indexCount / 3
  if (inventory.entries.length + triangleCount > NATIVE_TARGET_RGB24_MAX) throw new Error('Native primitive/target triangle key capacity exceeds RGB24')
  for (const entry of inventory.entries) assertNativeTargetTopology(entry)
  if (request.targetIndexOffset + 3 > target.record.indexCount || !nativeTargetTriangleActive(target, request.targetIndexOffset)) {
    throw new Error('Requested target triangle is outside the actual completed native triangle draw')
  }
  const position = original.getAttribute('position')
  const positionStorage = storage(position)
  const stride = position instanceof THREE.InterleavedBufferAttribute ? position.data.stride : 3
  const positionOffset = position instanceof THREE.InterleavedBufferAttribute ? position.offset : 0
  const classVertexIndices: number[] = []
  for (let row = 0; row < position.count; row++) {
    if (request.exactLocalPosition.every((coordinate, axis) => Object.is(coordinate, positionStorage[row * stride + positionOffset + axis]))) classVertexIndices.push(row)
  }
  if (!classVertexIndices.length) throw new Error('Requested exact Float32 coordinate class does not occur in the actual native target POSITION')
  const classVertices = new Set(classVertexIndices)
  const incidentTriangleIndexOffsets: number[] = []
  for (let offset = 0; offset < target.record.indexCount; offset += 3) {
    for (let corner = 0; corner < 3; corner++) {
      if (classVertices.has(original.index ? original.index.array[offset + corner]! : offset + corner)) {
        incidentTriangleIndexOffsets.push(offset)
        break
      }
    }
  }
  if (!incidentTriangleIndexOffsets.includes(request.targetIndexOffset)) throw new Error('Requested actual triangle does not contain the exact Float32 coordinate class')
  const inspection: NativeTargetSurfaceInspection = {
    request: { ...request, exactLocalPosition: [...request.exactLocalPosition], nativeStageBackingPixel: [...request.nativeStageBackingPixel] },
    model: { runtimeRootUuid: model.root.uuid, provenance: { ...model.provenance }, identityMapSha256: model.identityMapSha256,
      canonicalModelSha256: model.canonicalModelSha256, semanticSha256: model.semanticSha256 },
    machineRevision: token.machineRevision, inventoryRevision: token.inventoryRevision, input: nativeInputSnapshot(model.input), draw: structuredClone(draw),
    census: inventory.census, runtimeInstanceDeclarations: inventory.runtimeInstanceDeclarations,
    target: { object: target.object, record: target.record, primitiveId: target.record.id, canonicalPrimitiveId: target.record.identity.canonicalId,
      classVertexIndices, incidentTriangleIndexOffsets, triangleCount },
  }
  assertNativeTargetRequest(model, draw, token, request)
  return { inspection, nativeEntries: inventory.entries }
}

/** Explicit metadata-only inspection; no geometry/material or vertex-buffer copies. */
export function inspectNativeTargetSurfaceTarget(
  model: NativeCaptureModel,
  draw: NativePrimitiveDraw,
  token: NativeDrawStateToken,
  request: NativeTargetSurfaceRequest,
): NativeTargetSurfaceInspection {
  return inspectNativeTargetSurfaceRequest(model, draw, token, request).inspection
}

/**
 * One-request depth-native GPU preparation. No render target, rendering, readback,
 * CPU replay, full geometry capture or source acceptance occurs here. Scene swaps
 * these materials and ONLY the target geometry, then restores originals in finally.
 */
export function prepareNativeTargetSurfaceAssociation(
  model: NativeCaptureModel,
  draw: NativePrimitiveDraw,
  token: NativeDrawStateToken,
  request: NativeTargetSurfaceRequest,
): NativeTargetSurfacePass {
  const { inspection, nativeEntries } = inspectNativeTargetSurfaceRequest(model, draw, token, request)
  const { target } = inspection
  const { classVertexIndices, incidentTriangleIndexOffsets, triangleCount } = target
  const original = target.object.geometry
  // All request/topology/capacity guards precede temporary GPU resource creation.
  const diagnosticGeometry = new THREE.BufferGeometry()
  const ownedMaterials: THREE.Material[] = []
  let disposed = false
  const dispose = () => {
    if (disposed) return
    disposed = true
    diagnosticGeometry.dispose()
    for (const material of ownedMaterials) material.dispose()
  }
  try {
    copyNativeTargetAttributes(original, diagnosticGeometry, target.record.indexCount, nativeEntries.length)
    const idLookup = new Map<number, NativeTargetSurfaceId>()
    const entries = nativeEntries.map(({ object, record }, ordinal) => {
      const key = ordinal + 1
      const isTarget = object === target.object
      if (!isTarget) idLookup.set(key, { primitiveId: record.id, canonicalPrimitiveId: record.identity.canonicalId, triangleIndexOffset: null })
      const diagnostic = (material: THREE.Material) => {
        const clone = nativeTargetDiagnosticMaterial(material, key, isTarget)
        ownedMaterials.push(clone)
        return clone
      }
      return { object, originalMaterial: object.material,
        diagnosticMaterial: Array.isArray(object.material) ? object.material.map(diagnostic) : diagnostic(object.material) }
    })
    for (let ordinal = 0; ordinal < triangleCount; ordinal++) {
      idLookup.set(nativeEntries.length + 1 + ordinal, { primitiveId: target.record.id, canonicalPrimitiveId: target.record.identity.canonicalId, triangleIndexOffset: ordinal * 3 })
    }
    const ownedRequest = inspection.request
    const incidentOffsets = new Set(incidentTriangleIndexOffsets)
    const pass: NativeTargetSurfacePass = {
      ...inspection,
      method: 'current-native-depth-target-surface-association', equivalence: 'depth-native-not-colour-or-composite',
      entries,
      target: { ...target, originalGeometry: original, diagnosticGeometry, keyAttributeName: NATIVE_TARGET_TRIANGLE_KEY_ATTRIBUTE },
      idLookup, sourceProof: false, sourceAcceptance: false, numericVertexResidualBoundMetres: null, gpuPositionRoundingBoundMetres: null, eligibility: 'unresolved',
      decodePixel(pixel) {
        if (!(pixel instanceof Uint8Array) || pixel.length !== 4) throw new Error('Native target-surface decode requires exactly four raw RGBA8 bytes')
        const rawPixel: [number, number, number, number] = [pixel[0]!, pixel[1]!, pixel[2]!, pixel[3]!]
        const key = rawPixel[0] | rawPixel[1] << 8 | rawPixel[2] << 16
        const decoded = !disposed && rawPixel[3] === 255 ? idLookup.get(key) : undefined
        const status = disposed ? 'unresolved' : key === 0 && (rawPixel[3] === 0 || rawPixel[3] === 255) ? 'no-native-surface'
          : !decoded ? 'unresolved' : decoded.primitiveId !== target.record.id ? 'occluded-by-native-primitive'
            : decoded.triangleIndexOffset !== null && incidentOffsets.has(decoded.triangleIndexOffset) ? 'target-incident-triangle' : 'target-other-triangle'
        return {
          status, primitiveId: decoded?.primitiveId ?? null, canonicalPrimitiveId: decoded?.canonicalPrimitiveId ?? null,
          triangleIndexOffset: decoded?.triangleIndexOffset ?? null, requestedTriangleIndexOffset: ownedRequest.targetIndexOffset,
          targetClassVertexIndices: [...classVertexIndices], incidentTriangleIndexOffsets: [...incidentTriangleIndexOffsets], rawPixel,
          sourceProof: false, sourceAcceptance: false, numericVertexResidualBoundMetres: null, gpuPositionRoundingBoundMetres: null, eligibility: 'unresolved',
        }
      },
      dispose,
    }
    assertNativeTargetRequest(model, draw, token, request)
    return pass
  } catch (error) {
    dispose()
    throw error
  }
}
