import type * as THREE from 'three'
import type { Binding } from './bindings'
import type { CameraRecord, ImagePlaneWarp, PartOverride, Presentation, SourceComposite, SourceCompositeProvenance, SourceLayoutEntry } from './scene'
import type { SerializedInput, SourceImageIdentity } from './source-witness'

export type NativeQualificationCaptureMode = 'disabled' | 'enabled'
export type NativeProgramFamily = 'standard' | 'nativeID' | 'depth' | 'distance'
export type NativePresentationKind = 'source-warp' | 'horizontal-mirror' | 'source-composite'
export type NativePresentationSourceRole = 'native-colour-stage' | 'source-composite-image' | 'source-composite-sum' | null
export interface NativePresentationInventoryEntry {
  kind: NativePresentationKind
  object: THREE.Mesh
  readonly phase: 'source-presentation' | 'diagnostic-presentation'
  readonly inputTexture: THREE.Texture | null
  readonly sourceRole: NativePresentationSourceRole
}
export type NativeScalar = 'f32le' | 'f64le' | 'u32le' | 'u8'
export type NativeSerializedBinding = Omit<Binding, 'pattern'> & { pattern: { source: string; flags: string } }
export interface NativeByteSpan {
  objectSHA256: string
  objectByteLength: number
  byteOffset: number
  byteLength: number
  scalar: NativeScalar
  components: number
  count: number
}
export interface NativePrimitiveAssociation {
  nodeIndex: number | null
  meshIndex: number | null
  primitiveIndex: number | null
}
/** Real renderer-owned references. This is an internal bridge, not JSON evidence. */
export interface NativeQualificationInventoryEntry {
  path: string
  object: THREE.Mesh
  restMatrixWorldF64: ArrayLike<number>
  association: NativePrimitiveAssociation
  instanceOf: string | null
  bindingOwnerPath: string | null
  binding: Binding | null
  station: number | null
  spring: {
    stock: 'channel' | 'counter'
    restLengthM: number
    length: { value: number }
  } | null
}
export interface NativeDrawableSnapshot {
  path: string
  matrixWorld: Float64Array
  effectiveVisibility: 'visible' | 'hidden'
  groups: { start: number; count: number; materialIndex: number }[]
  drawRange: { start: number; count: number }
  materials: readonly THREE.Material[]
  bindingOwnerPath: string | null
  binding: Binding | null
  station: number | null
  springLengthM: number | null
}
/** Actual readback, before any JSON/content-addressed serialization. */
export interface NativeRasterCapture {
  pixels: Uint8Array
  width: number
  height: number
  origin: 'bottom-left'
  coordinateSpace: 'native-viewport' | 'source-stage'
  viewportBackingPixels: [number, number, number, number]
  encoding: 'rgba8' | 'path-id-rgb24-low-r' | 'three-rgba-depth-v1'
  depthBits: number | null
  targetSemantics: 'actual-production-material-offscreen' | 'depth-tested-native-id-diagnostic'
  sampleCount: 0
  textureColorSpace: string
  depthAttachment: { componentType: number; textureFormat: number; textureType: number } | null
}
export interface NativeSceneCapture {
  status: 'captured' | 'stale' | 'unavailable' | 'disposed'
  reason: string | null
  viewId: string
  drawRevision: number | null
  completedDrawEpoch: number | null
  timeSeconds: number | null
  camera: CameraRecord | null
  rectSourcePixels: readonly [number, number, number, number] | null
  presentation: Presentation | null
  sourceOpacity: number | null
  resolvedImagePlaneWarp: ImagePlaneWarp | null
  sourceLayout: SourceLayoutEntry[]
  nativeViewportBackingPixels: [number, number] | null
  sourceStageViewportBackingPixels: [number, number, number, number] | null
  sourceStageScissorBackingPixels: [number, number, number, number] | null
  destinationCellSourcePixels: [number, number]
  drawables: readonly NativeDrawableSnapshot[]
  nativeMaterialRGBA: NativeRasterCapture | null
  nativeMaterialDepth: NativeRasterCapture | null
  nativePathID: NativeRasterCapture | null
  nativeIDDepth: NativeRasterCapture | null
}
export interface NativeDrawBinding {
  sourceVideoId: string
  sourceSha256: string
  sourceImage: Extract<SourceImageIdentity, { pixelFormat: 'bgr8' }>
  decodedFrameIndex: number
  decodedTimestampTicks: string
  timeBase: string
  shotId: string
  viewId: string
  timeSeconds: number
  decodedTimeSeconds: number
  modelSourceCommit: string
  modelRawSHA256: string
  modelDeliverySHA256: string
  modelDeliveryByteLength: number
  currentBuildClosureSHA256: string
  input: SerializedInput
  inputSHA256: string
  camera: CameraRecord
  rectSourcePixels: readonly [number, number, number, number]
  presentation: Presentation
  composite: SourceComposite
  compositeProvenance: SourceCompositeProvenance | null
  imagePlaneWarp: ImagePlaneWarp | null
  resolvedImagePlaneWarp: ImagePlaneWarp | null
  sourceLayout: SourceLayoutEntry[]
  partOverrides: PartOverride[]
  sourceDrawRevision: number
  completedSceneDrawEpoch: number
}
export interface NativeStaticDrawable {
  path: string
  mode: 4
  ancestor: { rawNodeIndex: number; rawMeshIndex: number; rawPrimitiveIndex: number; rawPath: string; instanceOf: string | null }
  bindingOwnerPath: string | null
  binding: NativeSerializedBinding | null
  station: number | null
  attributes: { semantic: string; componentType: number; normalized: boolean; bytes: NativeByteSpan }[]
  canonicalIndices: NativeByteSpan
  restMatrixF64: NativeByteSpan
  spring: { stock: 'channel' | 'counter'; restLengthM: number; coordinate: NativeByteSpan; restCentre: NativeByteSpan; restTangent: NativeByteSpan } | null
}
export interface NativeStaticManifest {
  schemaVersion: 1
  rawSHA256: string
  deliverySHA256: string
  deliveryByteLength: number
  codeObjectSHA256: string
  drawables: NativeStaticDrawable[]
}
export interface NativeSubmittedPrimitive {
  path: string
  family: NativeProgramFamily
  vertexShader: NativeByteSpan
  fragmentShader: NativeByteSpan
  attributes: { name: string; componentType: number; normalized: boolean; stride: number; offset: number; divisor: number; enabled: boolean; bytes: NativeByteSpan }[]
  canonicalSubmittedIndices: NativeByteSpan
  drawRange: { start: number; count: number; mode: 4 }
  activeUniforms: { name: string; glType: number; arraySize: number; bytes: NativeByteSpan }[]
  matrixWorldF64: NativeByteSpan
  modelViewF64: NativeByteSpan
  projectionF64: NativeByteSpan
  geometryStateSHA256: string
}
export interface NativePresentationSubmission {
  kind: NativePresentationKind
  viewId: string
  phase: 'source-presentation' | 'diagnostic-presentation'
  sourceRole: NativePresentationSourceRole
  vertexShader: NativeByteSpan
  fragmentShader: NativeByteSpan
  activeUniforms: NativeSubmittedPrimitive['activeUniforms']
  attributes: NativeSubmittedPrimitive['attributes']
  canonicalSubmittedIndices: NativeByteSpan
  viewportBackingPixels: [number, number, number, number]
  scissorBackingPixels: [number, number, number, number]
  scissorTest: boolean
  drawRange: { start: number; count: number; mode: 4 }
  samplerBindings: { uniform: string; unit: number; boundMatchesMaterialTexture: boolean | null; textureUUID: string | null; textureVersion: number | null }[]
}
export type NativeNumericField = 'local' | 'world' | 'view' | 'clip' | 'objectNormal' | 'viewNormal' | 'springCentre' | 'springTangent'
export interface NativeNumericOutput {
  path: string
  family: NativeProgramFamily
  geometryStateSHA256: string
  submissionStateSHA256: string | null
  authority: 'epilogue-only-original-active-inputs'
  originalProgramSHA256: string
  instrumentationSource: NativeByteSpan
  output: NativeByteSpan
  fields: { name: NativeNumericField; offset: number; components: 3 | 4 }[]
  unavailable: { field: NativeNumericField; reason: 'not-consumed' | 'optimized-out' | 'uncaptured-replica-input' | 'not-selected-for-measured-tf' }[]
}
export interface NativeRasterPlane extends Omit<NativeRasterCapture, 'pixels'> {
  bytes: NativeByteSpan
}
export interface NativeViewReceipt {
  schemaVersion: 1
  binding: NativeDrawBinding
  staticNativeSHA256: string
  drawableStateSHA256: string
  submitted: NativeSubmittedPrimitive[]
  presentationSubmissions: NativePresentationSubmission[]
  numericOutputs: NativeNumericOutput[]
  raster: { nativeMaterialRGBA: NativeRasterPlane; nativeMaterialDepth: NativeRasterPlane; nativePathID: NativeRasterPlane; nativeIDDepth: NativeRasterPlane }
  rawCaseRetention: 'retained-selected-case' | 'streamed-live-only'
}
