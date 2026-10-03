import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { MeshoptDecoder } from 'meshoptimizer'
import modelRepresentation from '../content/model-representation.json'
import { assertModelRepresentationBytes, REPRESENTATION_KIND, REPRESENTATION_PATH } from '../model-representation.mjs'
import { BINDINGS, instanceIndex, type Binding } from './bindings'
import { createMechanismInput, createMechanismPose, solveMechanism, MECHANISM_DATA, type MechanismInput, type MechanismPose } from './mechanics'
import { PAPER_FEED_MULTIPLIER } from './kinematics'

export type Point3 = readonly [number, number, number]
export type Quaternion4 = readonly [number, number, number, number]
export interface CameraRecord {
  positionMetres: Point3
  quaternion: Quaternion4
  verticalFovDegrees: number
  /** Measured unmirrored viewport-local principal point; omitted means centre. */
  principalPointViewportPixels?: readonly [number, number]
}
export type InteractionMode = 'following-video' | 'exploring'
export type Presentation = 'native' | 'horizontal-mirror'
/** Rendered-image contributions, never native mesh material opacity. */
export type SourceComposite = { mode: 'opaque' } | { mode: 'crossfade'; groupId: string; imageLayerId: string; opacity: number }
export interface ImagePlaneWarp {
  kind: 'homography'
  unwarpedViewportPixels: readonly [number, number]
  renderToSourcePixels: readonly [number, number, number, number, number, number, number, number, number]
}
export interface SourceLayoutEntry {
  viewId: string
  rectSourcePixels: readonly [number, number, number, number]
  presentation: Presentation
  composite: SourceComposite | null
  resolvedImagePlaneWarp: ImagePlaneWarp | null
}
interface RenderedSourceSupport {
  resolvedImagePlaneWarp: ImagePlaneWarp | null
  sourceLayout: SourceLayoutEntry[]
  nativeViewportBackingPixels: [number, number] | null
  destinationCellSourcePixels: [number, number]
}
export interface SourceView {
  /** Stable view identity; GPU landmark captures are keyed by it. */
  id: string
  camera: CameraRecord
  /** Top-left source pixels, then width and height; source is 1920 × 1080. */
  rectSourcePixels: readonly [number, number, number, number]
  presentation?: Presentation
  composite?: SourceComposite
  imagePlaneWarp?: ImagePlaneWarp
}
/**
 * Diagnostic landmark located by exactly one of `partLocalMetres` (native node
 * frame of `partPath`) or `worldMetres`. With `partPath`, as every source
 * observation has, `worldMetres` is that part's CAD-world point at its
 * exported rest pose and follows the part's visibility and overrides; without
 * it, `worldMetres` is a stateless diagnostic point. Malformed anchors and
 * missing parts are reported unresolved, never guessed.
 */
export interface LandmarkAnchor {
  readonly id: string
  readonly partPath?: string
  readonly partLocalMetres?: Point3
  readonly worldMetres?: Point3
}
export interface LandmarkProbeAnchor {
  readonly id: string
  readonly state: 'measurable' | 'unresolved'
  readonly reason: string | null
}
/** GPU diagnostic markers attached to native nodes; never alters native geometry. */
export interface LandmarkProbe {
  readonly visibilityMode: 'depth-off-landmark-projection'
  readonly anchors: readonly LandmarkProbeAnchor[]
  readonly status: 'active' | 'disposed'
  dispose(): void
}
export type RenderedLandmarkState = 'rendered' | 'unresolved' | 'not-visible'
export interface RenderedLandmark {
  id: string
  state: RenderedLandmarkState
  /** Actual marker vertex in native world metres at this view's draw, independent of pixel eligibility. */
  worldMetres: [number, number, number] | null
  /** Null when worldMetres is available; otherwise why no draw-bound world coordinate is known. */
  worldReason: string | null
  /** CSS pixels from the canvas top-left, y down; continuous (pixel centres at +0.5). */
  canvasPixels: [number, number] | null
  /** 1920 × 1080 source-frame pixels, top-left origin, y down; continuous. */
  sourcePixels: [number, number] | null
  /** Euclidean source-pixel raster uncertainty, including the warp Jacobian. */
  uncertaintySourcePixels: number | null
  /** Per-axis raster/resampling quantization bound of canvasPixels, CSS pixels. */
  uncertaintyCanvasPixels: number | null
  reason: string | null
}
export interface RenderedLandmarks extends RenderedSourceSupport {
  method: 'gpu-readback'
  visibilityMode: 'depth-off-landmark-projection'
  status: 'captured'
  sourceOpacity: number
  viewId: string
  presentation: Presentation
  /** Source time given to the capturing renderViews; null for exploring render(). */
  timeSeconds: number | null
  landmarks: RenderedLandmark[]
}
/** All native drawable paths, not an anchor-selected subset. */
export interface PartVisibilityProbe {
  readonly visibilityMode: 'depth-tested-native-surfaces'
  readonly partPaths: readonly string[]
  readonly status: 'active' | 'disposed'
  dispose(): void
}
export interface RenderedPartVisibility extends RenderedSourceSupport {
  method: 'gpu-readback'
  visibilityMode: 'depth-tested-native-surfaces'
  status: 'captured' | 'stale' | 'unavailable' | 'disposed'
  viewId: string
  presentation: Presentation | null
  timeSeconds: number | null
  rectSourcePixels: readonly [number, number, number, number] | null
  /** Actual per-view camera, including normalization and resolved principal point. */
  camera: CameraRecord | null
  /** Zero source contribution excludes all native geometry from the witness. */
  sourceOpacity: number | null
  /** Backing-store samples; extents are [left, top, right, bottom], exclusive. */
  parts: {
    partPath: string
    status: 'visible' | 'not-visible'
    pixelCount: number
    canvasExtentPixels: [number, number, number, number] | null
    sourceExtentPixels: [number, number, number, number] | null
    /** Actual four-neighbour ID boundaries, including occlusion and ROI cuts. */
    contourSourcePixels: [number, number][]
    /** Full raster boundary count, before deterministic bounded sampling. */
    contourPixelCount: number
    /** Euclidean source-pixel raster/mirror quantization bound. */
    uncertaintySourcePixels: number | null
  }[]
}
export interface PartOverride {
  partPath: string
  visibility?: 'visible' | 'hidden'
  worldPositionMetres?: Point3
  worldQuaternion?: Quaternion4
}
export interface ModelProvenance {
  sourceCommit: string
  /** Pinned RAW native CAD identity, not an observation of downloaded bytes. */
  sourceSha256: string
  representationKind: typeof REPRESENTATION_KIND
  expectedSha256: string
  observedSha256: string | null
  expectedByteLength: number
  observedByteLength: number | null
  generator: string | null
  identity: 'matched' | 'mismatched' | 'unavailable'
  url: string
}
export interface Machine {
  readonly input: MechanismInput
  readonly pose: MechanismPose
  readonly missing: string[]
  readonly availability: 'available' | 'unavailable' | 'incompatible'
  readonly loadError: string | null
  readonly provenance: ModelProvenance
  readonly partPaths: readonly string[]
  /** Actual qualified native drawable paths; querying does not allocate GPU resources. */
  readonly nativeDrawablePartPaths: readonly string[]
  update(input: MechanismInput, overrides?: readonly PartOverride[]): void
  /** Add another genuine native part instance, sharing its original geometry. */
  addPartInstance(sourcePartPath: string, instancePath: string): 'added' | 'already-present' | 'missing-source'
  /** Diagnostic GPU markers on actual native nodes; install with Viewer.setLandmarkProbe. */
  createLandmarkProbe(anchors: readonly LandmarkAnchor[]): LandmarkProbe
  createPartVisibilityProbe(): PartVisibilityProbe
  /** Remove the native root from the scene and free its GPU resources and probes. */
  dispose(): void
}
export interface LoadMachineOptions {
  /** GLB location; defaults to the pinned harmonic-analyzer export. */
  url?: string
}

/** Predictable device-capacity refusal, before a prepared source sample is published. */
export class ViewCapacityError extends RangeError {
  constructor(message: string) {
    super(message)
    this.name = 'ViewCapacityError'
  }
}

export interface Viewer {
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  /**
   * Live exploring controls. OrbitControls fixes its orbit axis from camera.up
   * at construction, so a new up basis replaces this instance: never cache it
   * or attach listeners; its 'change' events reach createViewer's onControlsChange.
   */
  readonly controls: OrbitControls
  resize(): void
  /** Exploring/rest draw; captures landmarks under EXPLORING_VIEW_ID when a probe is installed. */
  render(): void
  /** Pure hardware/target-size check; never allocates targets or changes draw/camera state. */
  preflightViews(views: readonly SourceView[]): void
  renderViews(views: readonly SourceView[], beforeView: ((view: SourceView, index: number) => void) | undefined, timeSeconds: number): void
  applyCamera(record: CameraRecord): void
  setInteraction(mode: InteractionMode): void
  fitView(object?: THREE.Object3D): void
  /** Install a probe (disposing any previous one), or null to restore plain native rendering. */
  setLandmarkProbe(probe: LandmarkProbe | null): void
  /** Read the capture made by the most recent draw of viewId; never rerenders. */
  readRenderedLandmarks(viewId: string): RenderedLandmarks | null
  setPartVisibilityProbe(probe: PartVisibilityProbe | null): void
  readRenderedPartVisibility(viewId: string): RenderedPartVisibility
  /** Remove listeners/controls and dispose every viewer-owned GPU resource. */
  dispose(): void
}

export const EXPLORING_VIEW_ID = 'exploring'
const SOURCE_WIDTH = 1920
const SOURCE_HEIGHT = 1080
const FULL_FRAME: readonly [number, number, number, number] = [0, 0, SOURCE_WIDTH, SOURCE_HEIGHT]
const MODEL_URL = `${import.meta.env.BASE_URL}${REPRESENTATION_PATH}`
const Z = new THREE.Vector3(0, 0, 1)
const Y = new THREE.Vector3(0, 1, 0)

/** Diagnostic markers live only on this layer; native cameras never enable it. */
const PROBE_LAYER = 31
/** One bit per marker across RGBA8; additive blending keeps overlapping markers separable. */
const SLOTS_PER_PASS = 32
/** Independent one-cell witnesses of the actual GL viewport and its axis orientation. */
const REFERENCE_NDC = 0.75
const REFERENCE_SOURCE_LOW = (1 - REFERENCE_NDC) / 2
const ACCUMULATOR_STRIDE = 7
/** Bounded, deterministic raster readback samples; total coverage is separate. */
const RASTER_SAMPLE_LIMIT = 256

interface ProbeMarker {
  id: string
  /** Global marker slot; -1 when unresolved at probe creation. */
  slot: number
  reason: string | null
  object: THREE.Points | null
}
interface ProbeInternals {
  readonly markers: readonly ProbeMarker[]
  readonly passes: number
  readonly pass: { value: number }
  readonly pointSize: { value: number }
  readonly revision: { value: number }
}
const probeInternals = new WeakMap<LandmarkProbe, ProbeInternals>()

// The native deformation hooks rewrite these two includes, so the probe keeps them.
const MARKER_VERTEX = `
attribute float landmarkSlot;
uniform float landmarkPass;
uniform float landmarkPointSize;
varying float landmarkBit;
void main() {
#include <beginnormal_vertex>
#include <begin_vertex>
#include <project_vertex>
  float pass = floor((landmarkSlot + 0.5) / ${SLOTS_PER_PASS.toFixed(1)});
  landmarkBit = landmarkSlot - pass * ${SLOTS_PER_PASS.toFixed(1)};
  gl_PointSize = landmarkPointSize;
  if (abs(pass - landmarkPass) > 0.5) gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
}
`
const REFERENCE_VERTEX = `
attribute float landmarkSlot;
varying float landmarkBit;
void main() {
  landmarkBit = landmarkSlot;
  gl_PointSize = 1.0;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`
const MARKER_FRAGMENT = `
varying float landmarkBit;
void main() {
  float bit = floor(landmarkBit + 0.5);
  float channel = floor(bit / 8.0);
  float value = exp2(bit - channel * 8.0) / 255.0;
  gl_FragColor = vec4(channel == 0.0 ? value : 0.0, channel == 1.0 ? value : 0.0, channel == 2.0 ? value : 0.0, channel == 3.0 ? value : 0.0);
}
`

function markerMaterial(vertexShader: string, uniforms: Record<string, THREE.IUniform>): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms, vertexShader, fragmentShader: MARKER_FRAGMENT,
    depthTest: false, depthWrite: false,
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
    blendEquationAlpha: THREE.AddEquation, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneFactor,
  })
}

interface ViewCapture {
  epoch: number
  presentation: Presentation
  timeSeconds: number | null
  /** 0 rendered, 1 unresolved, 2 not-visible. */
  states: Uint8Array
  /** Per marker: canvas x/y, source x/y, uncertainty. */
  values: Float64Array
  sourceUncertainties: Float64Array
  reasons: (string | null)[]
  /** Rigid marker vertex transformed by matrixWorld immediately after this view's native draw. */
  worldValues: Float64Array
  worldReasons: (string | null)[]
  sourceOpacity: number
}
const CAPTURE_STATES: readonly RenderedLandmarkState[] = ['rendered', 'unresolved', 'not-visible']
interface NativeDrawable {
  path: string
  object: THREE.Mesh | THREE.Line | THREE.Points
  original: THREE.Material | THREE.Material[]
  diagnostic: THREE.Material | THREE.Material[]
}
interface PartVisibilityInternals {
  readonly entries: NativeDrawable[]
  readonly revision: { value: number }
  readonly inventoryRevision: { value: number }
  readonly synchronize: () => void
}
interface PartVisibilityCapture {
  epoch: number
  inventoryRevision: number
  presentation: Presentation
  timeSeconds: number | null
  rect: [number, number, number, number]
  sourceOpacity: number
  cameraValues: Float64Array
  /** Count, left, top, right, bottom, in backing-store coordinates. */
  values: Float64Array
  contourCounts: Uint32Array
  contourSampleCounts: Uint16Array
  /** Packed sample starts; invisible paths consume no coordinate capacity. */
  contourOffsets: Uint32Array
  /** Backing-store boundary pixel centres, not a bounding-box surrogate. */
  contourSamples: Float64Array
  uncertaintySourcePixels: number
}
const partVisibilityInternals = new WeakMap<PartVisibilityProbe, PartVisibilityInternals>()
const COMPOSITE_TOLERANCE = 1e-6
const compositeValidationGroups = new Set<string>()
const compositeValidationImages = new Set<string>()
const supportCache = new WeakMap<object, { valid: boolean; values: Float64Array; polygon: number[]; scratch: number[]; inverse: THREE.Matrix3; quantization: number }>()
const validationEdges: number[] = []
const validationCrossings: number[] = []
const validationCoveredImages = new Set<string>()

/** Convex source support, clipped separately from the native camera viewport. */
function sourceSupport(view: Pick<SourceView, 'rectSourcePixels' | 'imagePlaneWarp'>) {
  let cache = supportCache.get(view)
  if (!cache) {
    cache = { valid: false, values: new Float64Array(15).fill(NaN), polygon: [], scratch: [], inverse: new THREE.Matrix3(), quantization: 0 }
    supportCache.set(view, cache)
  }
  const rect = view.rectSourcePixels, warp = view.imagePlaneWarp
  if (rect.length !== 4) throw new Error('Source support requires a four-number rectangle.')
  if (warp && (warp.kind !== 'homography' || warp.unwarpedViewportPixels.length !== 2 || warp.renderToSourcePixels.length !== 9 || warp.unwarpedViewportPixels[0] <= 0 || warp.unwarpedViewportPixels[1] <= 0)) throw new Error('Invalid compiled source warp shape.')
  let changed = false
  for (let i = 0; i < 15; i++) {
    const value = i < 4 ? rect[i]! : i < 6 ? warp?.unwarpedViewportPixels[i - 4] ?? 0 : warp?.renderToSourcePixels[i - 6] ?? 0
    if (!Number.isFinite(value)) throw new Error('Source support requires finite numbers.')
    if (cache.values[i] !== value) { cache.values[i] = value; cache.valid = false; changed = true }
  }
  if (!changed && cache.valid) return cache
  cache.valid = false
  if (rect[2] <= 0 || rect[3] <= 0 || !Number.isFinite(rect[0] + rect[2]) || !Number.isFinite(rect[1] + rect[3])) throw new Error('Source support rectangle must have finite positive dimensions.')
  const polygon = cache.polygon
  polygon.length = 0
  cache.quantization = 0
  if (warp) {
    const [w, h] = warp.unwarpedViewportPixels, m = warp.renderToSourcePixels
    cache.inverse.set(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8])
    if (!Number.isFinite(cache.inverse.determinant()) || cache.inverse.determinant() === 0) throw new Error('Singular source image-plane warp.')
    cache.inverse.invert()
    let sign = 0, minimumDenominator = Infinity
    let numeratorXU = 0, numeratorXV = 0, numeratorYU = 0, numeratorYV = 0
    for (let corner = 0; corner < 4; corner++) {
      const u = corner === 1 || corner === 2 ? w : 0, v = corner >= 2 ? h : 0
      const d = m[6] * u + m[7] * v + m[8]
      if (d === 0 || (sign !== 0 && Math.sign(d) !== sign)) throw new Error('Source warp crosses a projective horizon.')
      sign = Math.sign(d)
      minimumDenominator = Math.min(minimumDenominator, Math.abs(d))
      const x = m[0] * u + m[1] * v + m[2], y = m[3] * u + m[4] * v + m[5]
      polygon.push(x / d, y / d)
      numeratorXU = Math.max(numeratorXU, Math.abs(m[0] * d - m[6] * x))
      numeratorXV = Math.max(numeratorXV, Math.abs(m[1] * d - m[7] * x))
      numeratorYU = Math.max(numeratorYU, Math.abs(m[3] * d - m[6] * y))
      numeratorYV = Math.max(numeratorYV, Math.abs(m[4] * d - m[7] * y))
    }
    // Derivative numerators are affine; extrema and denominator minimum occur
    // at corners. This bounds every native half-pixel cell over the whole image.
    cache.quantization = Math.hypot(numeratorXU * w / Math.ceil(w) + numeratorXV * h / Math.ceil(h), numeratorYU * w / Math.ceil(w) + numeratorYV * h / Math.ceil(h)) / (2 * minimumDenominator ** 2)
    if (!polygon.every(Number.isFinite) || !Number.isFinite(cache.quantization)) throw new Error('Nonfinite transformed source support.')
  } else polygon.push(rect[0], rect[1], rect[0] + rect[2], rect[1], rect[0] + rect[2], rect[1] + rect[3], rect[0], rect[1] + rect[3])
  for (let edge = 0; edge < 4; edge++) {
    const axis = edge % 2, lower = edge < 2
    const bound = lower ? Math.max(0, rect[axis]!) : Math.min(axis === 0 ? SOURCE_WIDTH : SOURCE_HEIGHT, rect[axis]! + rect[axis + 2]!)
    const scratch = cache.scratch
    scratch.length = 0
    for (let a = 0; a < polygon.length; a += 2) {
      const b = (a + 2) % polygon.length
      const da = (polygon[a + axis]! - bound) * (lower ? 1 : -1), db = (polygon[b + axis]! - bound) * (lower ? 1 : -1)
      if (da >= 0) scratch.push(polygon[a]!, polygon[a + 1]!)
      if ((da < 0) !== (db < 0)) {
        const t = da / (da - db)
        scratch.push(polygon[a]! + t * (polygon[b]! - polygon[a]!), polygon[a + 1]! + t * (polygon[b + 1]! - polygon[a + 1]!))
      }
    }
    polygon.length = 0
    for (const coordinate of scratch) polygon.push(coordinate)
  }
  cache.valid = true
  return cache
}

/** Exact positive-area arrangement slabs; one weight per image support union. */
export function assertSourceCompositeWeights(views: readonly Pick<SourceView, 'rectSourcePixels' | 'composite' | 'imagePlaneWarp'>[]): void {
  compositeValidationGroups.clear()
  for (const view of views) sourceSupport(view)
  for (let i = 0; i < views.length;) {
    const composite = views[i]!.composite
    if (!composite || composite.mode === 'opaque') { i++; continue }
    if (typeof composite.groupId !== 'string' || !composite.groupId || compositeValidationGroups.has(composite.groupId)) throw new Error('Crossfade groups must have a nonempty ID and contiguous views.')
    compositeValidationGroups.add(composite.groupId)
    compositeValidationImages.clear()
    const start = i
    let previousImage = '', previousOpacity = -1
    while (i < views.length) {
      const member = views[i]!.composite
      if (member?.mode !== 'crossfade' || member.groupId !== composite.groupId) break
      if (!Number.isFinite(member.opacity) || member.opacity < 0 || member.opacity > 1) throw new Error('Crossfade source opacity must be finite and in [0,1].')
      if (typeof member.imageLayerId !== 'string' || !member.imageLayerId) throw new Error('Crossfade requires an explicit imageLayerId.')
      if (previousImage !== member.imageLayerId) {
        if (compositeValidationImages.has(member.imageLayerId)) throw new Error('Crossfade images must have contiguous views.')
        compositeValidationImages.add(member.imageLayerId)
        previousImage = member.imageLayerId
        previousOpacity = member.opacity
      } else if (previousOpacity !== member.opacity) throw new Error('Views of one image must have identical opacity.')
      i++
    }
    validationEdges.length = 0
    for (let a = start; a < i; a++) {
      const p = sourceSupport(views[a]!).polygon
      for (let e = 0; e < p.length; e += 2) {
        validationEdges.push(p[e]!)
        const en = (e + 2) % p.length
        const ax = p[e]!, ay = p[e + 1]!, dx = p[en]! - ax, dy = p[en + 1]! - ay
        for (let b = a + 1; b < i; b++) {
          const q = sourceSupport(views[b]!).polygon
          for (let f = 0; f < q.length; f += 2) {
            const fn = (f + 2) % q.length, ex = q[fn]! - q[f]!, ey = q[fn + 1]! - q[f + 1]!
            const determinant = dx * ey - dy * ex
            if (determinant === 0) continue
            const rx = q[f]! - ax, ry = q[f + 1]! - ay
            const t = (rx * ey - ry * ex) / determinant, s = (rx * dy - ry * dx) / determinant
            if (t > 0 && t < 1 && s > 0 && s < 1) validationEdges.push(ax + t * dx)
          }
        }
      }
    }
    validationEdges.sort((a, b) => a - b)
    for (let slab = 1; slab < validationEdges.length; slab++) {
      if (validationEdges[slab] === validationEdges[slab - 1]) continue
      const x = (validationEdges[slab]! + validationEdges[slab - 1]!) / 2
      validationCrossings.length = 0
      for (let a = start; a < i; a++) {
        const p = sourceSupport(views[a]!).polygon
        for (let e = 0; e < p.length; e += 2) {
          const n = (e + 2) % p.length
          if ((p[e]! <= x && x < p[n]!) || (p[n]! <= x && x < p[e]!))
            validationCrossings.push(p[e + 1]! + (x - p[e]!) * (p[n + 1]! - p[e + 1]!) / (p[n]! - p[e]!))
        }
      }
      validationCrossings.sort((a, b) => a - b)
      for (let row = 1; row < validationCrossings.length; row++) {
        if (validationCrossings[row] === validationCrossings[row - 1]) continue
        const y = (validationCrossings[row]! + validationCrossings[row - 1]!) / 2
        validationCoveredImages.clear()
        let sum = 0
        for (let a = start; a < i; a++) {
          const member = views[a]!.composite
          if (member?.mode !== 'crossfade' || validationCoveredImages.has(member.imageLayerId)) continue
          const p = sourceSupport(views[a]!).polygon
          let inside = false
          for (let e = 0, previous = p.length - 2; e < p.length; previous = e, e += 2)
            if ((p[e + 1]! > y) !== (p[previous + 1]! > y) && x < (p[previous]! - p[e]!) * (y - p[e + 1]!) / (p[previous + 1]! - p[e + 1]!) + p[e]!) inside = !inside
          if (inside) { validationCoveredImages.add(member.imageLayerId); sum += member.opacity }
        }
        if (sum > 1 + COMPOSITE_TOLERANCE) throw new Error(`Crossfade group ${composite.groupId} image support weights exceed one: ${sum}.`)
      }
    }
  }
}

/** Every public OrbitControls tunable (three r180), carried across a basis rebuild. */
const ORBIT_SETTINGS = [
  'enabled', 'minDistance', 'maxDistance', 'minZoom', 'maxZoom', 'minTargetRadius', 'maxTargetRadius',
  'minPolarAngle', 'maxPolarAngle', 'minAzimuthAngle', 'maxAzimuthAngle', 'enableDamping', 'dampingFactor',
  'enableZoom', 'zoomSpeed', 'enableRotate', 'rotateSpeed', 'keyRotateSpeed', 'enablePan', 'panSpeed',
  'screenSpacePanning', 'keyPanSpeed', 'zoomToCursor', 'autoRotate', 'autoRotateSpeed', 'keys', 'mouseButtons',
  'touches', 'zoom0',
] as const satisfies readonly (keyof OrbitControls)[]

/**
 * Source cameras and every mechanical point remain in the original metre CAD
 * frame. `onControlsChange` receives every exploring-controls 'change' event,
 * across control rebuilds.
 */
export function createViewer(canvas: HTMLCanvasElement, onControlsChange: () => void): Viewer {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.autoClear = false
  const gl = renderer.getContext()
  // WebGL returns ALIASED_POINT_SIZE_RANGE as a Float32Array [min, max].
  const pointSizeRange: Float32Array = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE)
  const maxPointSize = pointSizeRange[1]!
  const maxRenderbufferSize = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE) as number
  const maxViewportDimensions = gl.getParameter(gl.MAX_VIEWPORT_DIMS) as Int32Array
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x11131a)
  // Native steel/brass are fully metallic: ambient diffuse light cannot reveal
  // their surfaces without image-based lighting. This room supplies reflections
  // only; its geometry is never added to the native scene or visibility census.
  const roomEnvironment = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  let environmentTarget: THREE.WebGLRenderTarget
  try {
    environmentTarget = pmrem.fromScene(roomEnvironment)
  } finally {
    roomEnvironment.dispose()
    pmrem.dispose()
  }
  scene.environment = environmentTarget.texture
  const camera = new THREE.PerspectiveCamera(35, SOURCE_WIDTH / SOURCE_HEIGHT, 0.005, 100)
  camera.setViewOffset(SOURCE_WIDTH, SOURCE_HEIGHT, 0, 0, SOURCE_WIDTH, SOURCE_HEIGHT)
  camera.clearViewOffset()
  camera.position.set(1.2, 1, 1.6)
  // The orbit basis the live controls were constructed for (camera.up then).
  const controlsUp = camera.up.clone()
  let controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 0.68, 0)
  controls.enableDamping = false
  controls.addEventListener('change', onControlsChange)
  let mode: InteractionMode = 'exploring'
  scene.add(new THREE.HemisphereLight(0xffffff, 0x404050, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(2, 3, 2)
  scene.add(key)

  const gate = { x: 0, y: 0, width: 1, height: 1 }
  const forward = new THREE.Vector3()
  const bounds = new THREE.Box3()
  const box = new THREE.Box3()
  const centre = new THREE.Vector3()
  const size = new THREE.Vector3()
  const savedPosition = new THREE.Vector3()
  const savedQuaternion = new THREE.Quaternion()
  const mirrorTarget = new THREE.WebGLRenderTarget(1, 1)
  const mirrorScene = new THREE.Scene()
  const mirrorCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
  const mirrorMaterial = new THREE.ShaderMaterial({
    uniforms: { image: { value: mirrorTarget.texture } },
    vertexShader: 'varying vec2 imageUv; void main() { imageUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }',
    fragmentShader: 'uniform sampler2D image; varying vec2 imageUv; void main() { gl_FragColor=texture2D(image,vec2(1.0-imageUv.x,imageUv.y));\n#include <colorspace_fragment>\n}',
    depthTest: false, depthWrite: false,
  })
  // This screen-space blit is presentation only, never replacement machine geometry.
  const quadGeometry = new THREE.PlaneGeometry(2, 2)
  mirrorScene.add(new THREE.Mesh(quadGeometry, mirrorMaterial))
  const warpScene = new THREE.Scene()
  const warpInverse = new THREE.Matrix3()
  const warpGrid = new THREE.Vector2()
  const warpRect = new THREE.Vector4()
  const sourceFromBacking = new THREE.Vector4()
  const warpMaterial = new THREE.ShaderMaterial({
    uniforms: { image: { value: mirrorTarget.texture }, inverseH: { value: warpInverse }, grid: { value: warpGrid },
      sourceFromBacking: { value: sourceFromBacking }, rect: { value: warpRect }, warped: { value: false }, mask: { value: false } },
    vertexShader: mirrorMaterial.vertexShader,
    fragmentShader: `uniform sampler2D image; uniform mat3 inverseH; uniform vec2 grid;
uniform vec4 sourceFromBacking; uniform vec4 rect; uniform bool warped; uniform bool mask;
void main() {
  vec2 source = gl_FragCoord.xy * sourceFromBacking.xy + sourceFromBacking.zw;
  if (any(lessThan(source, rect.xy)) || any(greaterThanEqual(source, rect.xy + rect.zw))) discard;
  vec3 local = inverseH * vec3(source, 1.0);
  vec2 p = warped ? local.xy / local.z : source - rect.xy;
  vec2 dimensions = warped ? grid : rect.zw;
  if (any(lessThan(p, vec2(0.0))) || any(greaterThanEqual(p, dimensions))) discard;
  if (mask) { gl_FragColor = vec4(0.0); return; }
  gl_FragColor = texture2D(image, vec2(p.x / dimensions.x, 1.0 - p.y / dimensions.y));
  #include <colorspace_fragment>
}`,
    depthTest: false, depthWrite: false, blending: THREE.NoBlending, toneMapped: false,
  })
  warpScene.add(new THREE.Mesh(quadGeometry, warpMaterial))
  let activeView: SourceView | null = null
  let activeViewIndex = -1
  let diagnosticDraw = false
  const compositeScene = new THREE.Scene()
  const compositeImageRect = new THREE.Vector4()
  const compositeBackground = new THREE.Color()
  const compositeMaterial = new THREE.ShaderMaterial({
    uniforms: { image: { value: null }, imageRect: { value: compositeImageRect }, weight: { value: 1 }, background: { value: compositeBackground }, stage: { value: 0 } },
    vertexShader: mirrorMaterial.vertexShader,
    // Accumulate encoded image colours with their measured per-pixel weights:
    // sequential alpha OVER would attenuate earlier contributions. Alpha here
    // records local ROI support, not a global sum of disjoint image weights.
    fragmentShader: `uniform sampler2D image; uniform vec4 imageRect; uniform float weight;
uniform vec3 background; uniform float stage; varying vec2 imageUv;
void main() {
  vec4 layer = texture2D(image, imageRect.xy + imageUv * imageRect.zw);
  vec3 colour = layer.rgb;
  if (stage < 0.5) {
    colour = mix(12.92 * colour, 1.055 * pow(max(colour, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), colour));
    gl_FragColor = vec4(colour * weight * layer.a, weight * layer.a);
  } else {
    if (layer.a <= 0.0) discard;
    gl_FragColor = vec4(colour + background * max(0.0, 1.0 - layer.a), 1.0);
  }
}`,
    depthTest: false, depthWrite: false, toneMapped: false,
  })
  compositeScene.add(new THREE.Mesh(quadGeometry, compositeMaterial))
  let compositeImageTarget: THREE.WebGLRenderTarget | null = null
  let compositeSumTarget: THREE.WebGLRenderTarget | null = null

  // GPU landmark readback state. Targets/buffers allocate on first capture or
  // actual size change only; the steady-state frame loop allocates nothing.
  let probe: LandmarkProbe | null = null
  let probeTarget: THREE.WebGLRenderTarget | null = null
  let probeMirrorTarget: THREE.WebGLRenderTarget | null = null
  let readback = new Uint8Array(0)
  let readbackWords = new Uint32Array(0)
  const accumulators = new Float64Array(SLOTS_PER_PASS * ACCUMULATOR_STRIDE)
  const captures = new Map<string, ViewCapture>()
  let drawEpoch = 0
  let disposed = false
  let renderedProbeRevision = -1
  let visibilityProbe: PartVisibilityProbe | null = null
  let renderedVisibilityRevision = -1
  let visibilityTarget: THREE.WebGLRenderTarget | null = null
  let visibilityMirrorTarget: THREE.WebGLRenderTarget | null = null
  let visibilityPixels = new Uint8Array(0)
  let contourOrdinals = new Uint32Array(0)
  let contourFlags = new Uint8Array(0)
  const visibilityCaptures = new Map<string, PartVisibilityCapture>()
  const viewSnapshots = new Map<string, { epoch: number; view: SourceView; groupId: string | null; imageLayerId: string | null; id: string; warpKind: string | null; presentation: Presentation; values: Float64Array }>()
  const frameCameraPosition = new THREE.Vector3()
  const frameCameraQuaternion = new THREE.Quaternion()
  const frameCameraProjection = new THREE.Matrix4()
  let frameWidth = 0
  let frameHeight = 0
  let frameFov = 0
  let frameAspect = 0
  let renderedViews: readonly SourceView[] | null = null
  const capturedViewOrder: SourceView[] = []
  const probeViewport = new THREE.Vector4()
  const viewScissorPixels = new THREE.Vector4()
  const savedClearColor = new THREE.Color()
  const referenceGeometry = new THREE.BufferGeometry()
  referenceGeometry.setAttribute('position', new THREE.Float32BufferAttribute([-REFERENCE_NDC, REFERENCE_NDC, 0, REFERENCE_NDC, -REFERENCE_NDC, 0], 3))
  referenceGeometry.setAttribute('landmarkSlot', new THREE.Float32BufferAttribute([0, 1], 1))
  const referenceMaterial = markerMaterial(REFERENCE_VERTEX, {})
  const referencePoints = new THREE.Points(referenceGeometry, referenceMaterial)
  referencePoints.frustumCulled = false
  const referenceScene = new THREE.Scene()
  referenceScene.add(referencePoints)

  function resize() {
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    if (w === 0 || h === 0) return
    renderer.setSize(w, h, false)
    gate.width = Math.min(w, h * SOURCE_WIDTH / SOURCE_HEIGHT)
    gate.height = gate.width * SOURCE_HEIGHT / SOURCE_WIDTH
    gate.x = (w - gate.width) / 2
    gate.y = (h - gate.height) / 2
    camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
    camera.updateProjectionMatrix()
    mirrorTarget.setSize(Math.max(1, Math.round(gate.width * renderer.getPixelRatio())), Math.max(1, Math.round(gate.height * renderer.getPixelRatio())))
    // Resizing clears the canvas; earlier captures no longer describe it.
    drawEpoch++
  }
  addEventListener('resize', resize)

  function writeCamera(target: THREE.PerspectiveCamera, record: CameraRecord, width: number, height: number) {
    target.position.fromArray(record.positionMetres)
    target.quaternion.fromArray(record.quaternion).normalize()
    target.fov = record.verticalFovDegrees
    target.aspect = width / height
    const principal = record.principalPointViewportPixels
    if (principal) target.setViewOffset(width, height, width / 2 - principal[0], height / 2 - principal[1], width, height)
    else target.clearViewOffset()
    target.updateMatrixWorld(true)
  }

  // OrbitControls derives its orbit axis from camera.up once, in its
  // constructor, and update() keeps using that cached basis; three r180 has
  // no public way to change it. A new up basis therefore needs a new
  // instance carrying every public setting, the target and the change listener.
  function syncControlsBasis() {
    if (camera.up.equals(controlsUp)) return
    const previous = controls
    previous.removeEventListener('change', onControlsChange)
    previous.dispose()
    savedPosition.copy(camera.position)
    savedQuaternion.copy(camera.quaternion)
    const next = new OrbitControls(camera, canvas)
    // Its constructor's update() aimed the camera at the default origin target.
    camera.position.copy(savedPosition)
    camera.quaternion.copy(savedQuaternion)
    Object.assign(next, Object.fromEntries(ORBIT_SETTINGS.map(key => [key, previous[key]])))
    next.target.copy(previous.target)
    next.cursor.copy(previous.cursor)
    next.target0.copy(previous.target0)
    next.position0.copy(previous.position0)
    next.addEventListener('change', onControlsChange)
    controls = next
    controlsUp.copy(camera.up)
  }

  // Rebuild OrbitControls from the exact current pose, including roll. It
  // orbits about the camera's own up axis: forward stays perpendicular to it
  // (polar angle π/2, clear of the poles) and lookAt reproduces the exact roll.
  function rebaseControls() {
    const distance = Math.max(camera.position.distanceTo(controls.target), 0.1)
    forward.set(0, 0, -1).applyQuaternion(camera.quaternion)
    camera.up.set(0, 1, 0).applyQuaternion(camera.quaternion)
    syncControlsBasis()
    controls.target.copy(camera.position).addScaledVector(forward, distance)
    controls.update()
  }

  function applyCamera(record: CameraRecord) {
    drawEpoch++
    writeCamera(camera, record, SOURCE_WIDTH, SOURCE_HEIGHT)
    if (mode === 'exploring') rebaseControls()
  }

  function setInteraction(next: InteractionMode) {
    if (next === mode) return
    mode = next
    drawEpoch++
    controls.enabled = next === 'exploring'
    if (next === 'exploring') rebaseControls()
  }

  function fitView(object: THREE.Object3D = scene) {
    // Native geometry only: diagnostic markers must not move the operator view.
    bounds.makeEmpty()
    object.updateWorldMatrix(true, true)
    object.traverse(node => {
      if (node.userData.landmarkMarker || !(node instanceof THREE.Mesh || node instanceof THREE.Line || node instanceof THREE.Points)) return
      const geometry = node.geometry
      if (!geometry.boundingBox) geometry.computeBoundingBox()
      bounds.union(box.copy(geometry.boundingBox!).applyMatrix4(node.matrixWorld))
    })
    if (bounds.isEmpty()) return
    bounds.getCenter(centre)
    bounds.getSize(size)
    const radius = size.length() / 2
    camera.fov = 35
    camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
    camera.clearViewOffset()
    const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))
    forward.set(1, 0.25, 1.4).normalize()
    camera.position.copy(centre).addScaledVector(forward, distance)
    camera.up.set(0, 1, 0)
    controls.target.copy(centre)
    camera.lookAt(centre)
    camera.updateProjectionMatrix()
    camera.updateMatrixWorld(true)
    if (mode === 'exploring') {
      syncControlsBasis()
      controls.update()
    }
  }

  function beginFrame() {
    renderer.setRenderTarget(null)
    renderer.setScissorTest(false)
    renderer.setViewport(0, 0, canvas.clientWidth, canvas.clientHeight)
    renderer.clear(true, true, true)
    renderer.setScissorTest(true)
  }

  function viewport(x: number, y: number, width: number, height: number) {
    const left = gate.x + x / SOURCE_WIDTH * gate.width
    const top = gate.y + y / SOURCE_HEIGHT * gate.height
    const w = width / SOURCE_WIDTH * gate.width
    const h = height / SOURCE_HEIGHT * gate.height
    const bottom = canvas.clientHeight - top - h
    renderer.setViewport(left, bottom, w, h)
    // Shared half-open source support is defined by destination pixel centres,
    // not independently rounded viewport widths (which overlap at panel seams).
    // Preserve the native camera viewport; crop only its actual raster support.
    const scaleX = gl.drawingBufferWidth / canvas.clientWidth
    const scaleY = gl.drawingBufferHeight / canvas.clientHeight
    const x0 = Math.max(0, Math.min(gl.drawingBufferWidth, Math.ceil(left * scaleX - 0.5)))
    const x1 = Math.max(x0, Math.min(gl.drawingBufferWidth, Math.ceil((gate.x + (x + width) / SOURCE_WIDTH * gate.width) * scaleX - 0.5)))
    const topPixel = Math.max(0, Math.min(gl.drawingBufferHeight, Math.ceil(top * scaleY - 0.5)))
    const bottomPixel = Math.max(topPixel, Math.min(gl.drawingBufferHeight, Math.ceil((gate.y + (y + height) / SOURCE_HEIGHT * gate.height) * scaleY - 0.5)))
    viewScissorPixels.set(x0, gl.drawingBufferHeight - bottomPixel, x1 - x0, bottomPixel - topPixel)
    const ratio = renderer.getPixelRatio()
    renderer.setScissor(viewScissorPixels.x / ratio, viewScissorPixels.y / ratio, viewScissorPixels.z / ratio, viewScissorPixels.w / ratio)
  }

  function configureSupport(view: SourceView, mask: boolean) {
    const warp = view.imagePlaneWarp, rect = view.rectSourcePixels
    warpInverse.copy(sourceSupport(view).inverse)
    warpGrid.set(warp?.unwarpedViewportPixels[0] ?? rect[2], warp?.unwarpedViewportPixels[1] ?? rect[3])
    warpRect.fromArray(rect)
    const sx = SOURCE_WIDTH / gate.width * canvas.clientWidth / gl.drawingBufferWidth
    const sy = SOURCE_HEIGHT / gate.height * canvas.clientHeight / gl.drawingBufferHeight
    sourceFromBacking.set(sx, -sy, -gate.x * SOURCE_WIDTH / gate.width, (canvas.clientHeight - gate.y) * SOURCE_HEIGHT / gate.height)
    warpMaterial.uniforms.warped!.value = !!warp
    warpMaterial.uniforms.mask!.value = mask
  }

  function maskHigherViews(output: THREE.WebGLRenderTarget, rect: readonly [number, number, number, number]) {
    const composite = activeView?.composite
    if (!renderedViews || composite?.mode !== 'crossfade') return
    for (let i = activeViewIndex + 1; i < renderedViews.length; i++) {
      const view = renderedViews[i]!, member = view.composite
      if (member?.mode !== 'crossfade' || member.groupId !== composite.groupId || member.imageLayerId !== composite.imageLayerId) break
      configureSupport(view, true)
      renderer.setRenderTarget(output)
      renderer.setScissorTest(true)
      viewport(view.rectSourcePixels[0], view.rectSourcePixels[1], view.rectSourcePixels[2], view.rectSourcePixels[3])
      renderer.render(warpScene, mirrorCamera)
    }
    viewport(rect[0], rect[1], rect[2], rect[3])
  }

  function supportIntersects(polygon: readonly number[], left: number, top: number, right: number, bottom: number) {
    if (polygon.length < 6) return false
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (let j = 0; j < polygon.length; j += 2) {
      minX = Math.min(minX, polygon[j]!)
      minY = Math.min(minY, polygon[j + 1]!)
      maxX = Math.max(maxX, polygon[j]!)
      maxY = Math.max(maxY, polygon[j + 1]!)
    }
    if (right < minX || left > maxX || bottom < minY || top > maxY) return false
    // Separating axes of the actual convex source mask, not its camera ROI.
    for (let j = 0; j < polygon.length; j += 2) {
      const next = (j + 2) % polygon.length
      const nx = polygon[next + 1]! - polygon[j + 1]!, ny = polygon[j]! - polygon[next]!
      let minProjection = Infinity, maxProjection = -Infinity
      for (let k = 0; k < polygon.length; k += 2) {
        const projection = nx * polygon[k]! + ny * polygon[k + 1]!
        minProjection = Math.min(minProjection, projection)
        maxProjection = Math.max(maxProjection, projection)
      }
      const rectangleMin = nx * (nx < 0 ? right : left) + ny * (ny < 0 ? bottom : top)
      const rectangleMax = nx * (nx < 0 ? left : right) + ny * (ny < 0 ? top : bottom)
      if (rectangleMax < minProjection || rectangleMin > maxProjection) return false
    }
    return true
  }

  function higherMaskIntersects(left: number, top: number, right: number, bottom: number) {
    const composite = activeView?.composite
    if (!renderedViews || composite?.mode !== 'crossfade') return false
    for (let i = activeViewIndex + 1; i < renderedViews.length; i++) {
      const view = renderedViews[i]!, member = view.composite
      if (member?.mode !== 'crossfade' || member.groupId !== composite.groupId || member.imageLayerId !== composite.imageLayerId) break
      if (supportIntersects(sourceSupport(view).polygon, left, top, right, bottom)) return true
    }
    return false
  }

  function sourcePointSupported(view: SourceView, x: number, y: number, inverse: readonly number[] | null) {
    const rect = view.rectSourcePixels
    if (x < 0 || y < 0 || x >= SOURCE_WIDTH || y >= SOURCE_HEIGHT
      || x < rect[0] || y < rect[1] || x >= rect[0] + rect[2] || y >= rect[1] + rect[3]) return false
    const warp = view.imagePlaneWarp
    if (!warp) return true
    const m = inverse!
    const d = m[2]! * x + m[5]! * y + m[8]!
    const u = (m[0]! * x + m[3]! * y + m[6]!) / d
    const v = (m[1]! * x + m[4]! * y + m[7]!) / d
    return u >= 0 && v >= 0 && u < warp.unwarpedViewportPixels[0] && v < warp.unwarpedViewportPixels[1]
  }

  function sourceRegionUnmasked(left: number, top: number, right: number, bottom: number) {
    if (!activeView) return false
    const inverse = activeView.imagePlaneWarp ? sourceSupport(activeView).inverse.elements : null
    if (!sourcePointSupported(activeView, left, top, inverse) || !sourcePointSupported(activeView, left, bottom, inverse)
      || !sourcePointSupported(activeView, right, top, inverse) || !sourcePointSupported(activeView, right, bottom, inverse)) return false
    if (!renderedViews) return true
    const own = activeView.composite
    for (let i = activeViewIndex + 1; i < renderedViews.length; i++) {
      const view = renderedViews[i]!, later = view.composite
      const sameGroup = own?.mode === 'crossfade' && later?.mode === 'crossfade' && own.groupId === later.groupId
      const sameImage = sameGroup && own.imageLayerId === later.imageLayerId
      if (sameGroup && !sameImage) continue
      if ((sameImage || !later || later.mode === 'opaque' || later.opacity === 1)
        && supportIntersects(sourceSupport(view).polygon, left, top, right, bottom)) return false
    }
    return true
  }

  function viewportSourceDiscrepancy(rect: readonly [number, number, number, number], sourcePerPixelX: number, sourcePerPixelY: number) {
    if (activeView?.imagePlaneWarp) return 0
    const left = probeViewport.x * sourcePerPixelX - gate.x * SOURCE_WIDTH / gate.width - rect[0]
    const top = (gl.drawingBufferHeight - probeViewport.y - probeViewport.w) * sourcePerPixelY - gate.y * SOURCE_HEIGHT / gate.height - rect[1]
    return Math.hypot(
      Math.max(Math.abs(left), Math.abs(left + probeViewport.z * sourcePerPixelX - rect[2])),
      Math.max(Math.abs(top), Math.abs(top + probeViewport.w * sourcePerPixelY - rect[3])),
    )
  }

  function warpQuantization() {
    return activeView?.imagePlaneWarp ? sourceSupport(activeView).quantization : 0
  }

  function capturedSupport(viewId: string): RenderedSourceSupport {
    const snapshot = viewSnapshots.get(viewId)
    const view = snapshot?.epoch === drawEpoch ? snapshot.view : undefined
    const warp = view?.imagePlaneWarp
    // Public readbacks own copies: callers cannot mutate retained capture state.
    const copyWarp = (value: ImagePlaneWarp | undefined): ImagePlaneWarp | null => value ? { kind: 'homography', unwarpedViewportPixels: [...value.unwarpedViewportPixels], renderToSourcePixels: [...value.renderToSourcePixels] } : null
    return {
      resolvedImagePlaneWarp: copyWarp(warp),
      nativeViewportBackingPixels: warp ? [Math.ceil(warp.unwarpedViewportPixels[0]), Math.ceil(warp.unwarpedViewportPixels[1])] : null,
      destinationCellSourcePixels: [SOURCE_WIDTH / gate.width * canvas.clientWidth / gl.drawingBufferWidth, SOURCE_HEIGHT / gate.height * canvas.clientHeight / gl.drawingBufferHeight],
      sourceLayout: capturedViewOrder.map(member => ({ viewId: member.id, rectSourcePixels: [...member.rectSourcePixels], presentation: member.presentation ?? 'native', composite: member.composite ? { ...member.composite } : null, resolvedImagePlaneWarp: copyWarp(member.imagePlaneWarp) })),
    }
  }

  /**
   * One view's draw into `output` (null = canvas). The landmark probe calls
   * this same function, so its markers take the identical viewport/scissor
   * calls, mirror stage and blit as the native image.
   */
  function drawView(rect: readonly [number, number, number, number], presentation: Presentation, output: THREE.WebGLRenderTarget | null, mirrorStage: THREE.WebGLRenderTarget, clearOutput: boolean) {
    const warp = activeView?.imagePlaneWarp
    if (warp) {
      const width = Math.ceil(warp.unwarpedViewportPixels[0]), height = Math.ceil(warp.unwarpedViewportPixels[1])
      if (mirrorStage.width !== width || mirrorStage.height !== height) mirrorStage.setSize(width, height)
      renderer.setRenderTarget(mirrorStage)
      renderer.setScissorTest(false)
      renderer.clear(true, true, true)
      renderer.render(scene, camera)
      renderer.setRenderTarget(output)
      renderer.setScissorTest(true)
      viewport(rect[0], rect[1], rect[2], rect[3])
      // Native colour preserves previous layers outside the quad. Diagnostic
      // targets clear the ROI first so old pass bits cannot survive.
      if (diagnosticDraw) renderer.clear(true, true, false)
      else renderer.clear(false, true, false)
      configureSupport(activeView!, false)
      warpMaterial.uniforms.image!.value = mirrorStage.texture
      renderer.render(warpScene, mirrorCamera)
      if (diagnosticDraw && output) maskHigherViews(output, rect)
      return
    }
    if (presentation === 'horizontal-mirror') {
      // A preceding warp may have resized this shared stage to its native grid.
      const width = Math.max(1, Math.round(gate.width * renderer.getPixelRatio()))
      const height = Math.max(1, Math.round(gate.height * renderer.getPixelRatio()))
      if (mirrorStage.width !== width || mirrorStage.height !== height) mirrorStage.setSize(width, height)
      // The mirror stage uses its own full viewport with scissor disabled;
      // renderer.setViewport would wrongly scale it by the canvas pixel ratio.
      renderer.setRenderTarget(mirrorStage)
      renderer.setScissorTest(false)
      renderer.clear(true, true, true)
      renderer.render(scene, camera)
      renderer.setRenderTarget(output)
      renderer.setScissorTest(true)
      viewport(rect[0], rect[1], rect[2], rect[3])
      if (clearOutput) renderer.clear(true, true, false)
      mirrorMaterial.uniforms.image!.value = mirrorStage.texture
      renderer.render(mirrorScene, mirrorCamera)
    } else {
      renderer.setRenderTarget(output)
      renderer.setScissorTest(true)
      viewport(rect[0], rect[1], rect[2], rect[3])
      if (clearOutput) renderer.clear(true, true, false)
      renderer.render(scene, camera)
    }
    if (diagnosticDraw && output) maskHigherViews(output, rect)
  }

  function ensureCompositeTargets() {
    const width = gl.drawingBufferWidth
    const height = gl.drawingBufferHeight
    if (!compositeImageTarget) compositeImageTarget = new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType, samples: gl.getParameter(gl.SAMPLES) as number })
    else if (compositeImageTarget.width !== width || compositeImageTarget.height !== height) compositeImageTarget.setSize(width, height)
    if (!compositeSumTarget) compositeSumTarget = new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType, depthBuffer: false })
    else if (compositeSumTarget.width !== width || compositeSumTarget.height !== height) compositeSumTarget.setSize(width, height)
  }


  function compositeBlit(rect: readonly [number, number, number, number], output: THREE.WebGLRenderTarget | null, image: THREE.WebGLRenderTarget) {
    renderer.setRenderTarget(output)
    renderer.setScissorTest(true)
    viewport(rect[0], rect[1], rect[2], rect[3])
    renderer.getCurrentViewport(probeViewport)
    compositeImageRect.set(probeViewport.x / image.width, probeViewport.y / image.height, probeViewport.z / image.width, probeViewport.w / image.height)
    compositeMaterial.uniforms.image!.value = image.texture
    renderer.render(compositeScene, mirrorCamera)
  }

  function snapshotView(view: SourceView) {
    if (!probe && !visibilityProbe) return
    let snapshot = viewSnapshots.get(view.id)
    if (!snapshot) {
      snapshot = { epoch: -1, view, groupId: null, imageLayerId: null, id: view.id, warpKind: null, presentation: 'native', values: new Float64Array(27) }
      viewSnapshots.set(view.id, snapshot)
    }
    snapshot.epoch = drawEpoch
    snapshot.view = view
    snapshot.groupId = view.composite?.mode === 'crossfade' ? view.composite.groupId : null
    snapshot.presentation = view.presentation ?? 'native'
    snapshot.id = view.id
    snapshot.imageLayerId = view.composite?.mode === 'crossfade' ? view.composite.imageLayerId : null
    snapshot.warpKind = view.imagePlaneWarp?.kind ?? null
    for (let i = 0; i < 11; i++) snapshot.values[i + 15] = i < 2 ? view.imagePlaneWarp?.unwarpedViewportPixels[i] ?? NaN : view.imagePlaneWarp?.renderToSourcePixels[i - 2] ?? NaN
    const values = snapshot.values
    for (let i = 0; i < 3; i++) values[i] = view.camera.positionMetres[i]!
    for (let i = 0; i < 4; i++) values[i + 3] = view.camera.quaternion[i]!
    values[7] = view.camera.verticalFovDegrees
    values[8] = view.camera.principalPointViewportPixels?.[0] ?? NaN
    values[9] = view.camera.principalPointViewportPixels?.[1] ?? NaN
    for (let i = 0; i < 4; i++) values[i + 10] = view.rectSourcePixels[i]!
    values[14] = view.composite?.mode === 'crossfade' ? view.composite.opacity : 1
    values[26] = view.composite ? view.composite.mode === 'opaque' ? 1 : 2 : 0
  }

  function capturesFresh() {
    if (frameWidth !== canvas.clientWidth || frameHeight !== canvas.clientHeight || frameFov !== camera.fov || frameAspect !== camera.aspect
      || !frameCameraPosition.equals(camera.position) || !frameCameraQuaternion.equals(camera.quaternion) || !frameCameraProjection.equals(camera.projectionMatrix)) return false
    if (renderedViews) {
      if (renderedViews.length !== capturedViewOrder.length) return false
      for (let i = 0; i < renderedViews.length; i++) if (renderedViews[i] !== capturedViewOrder[i]) return false
    }
    for (const snapshot of viewSnapshots.values()) {
      if (snapshot.epoch !== drawEpoch) continue
      const view = snapshot.view
      const values = snapshot.values
      if (view.rectSourcePixels.length !== 4 || (view.imagePlaneWarp && (view.imagePlaneWarp.unwarpedViewportPixels.length !== 2 || view.imagePlaneWarp.renderToSourcePixels.length !== 9))) return false
      if (values[26] !== (view.composite ? view.composite.mode === 'opaque' ? 1 : 2 : 0)) return false
      if (snapshot.groupId !== (view.composite?.mode === 'crossfade' ? view.composite.groupId : null) || snapshot.presentation !== (view.presentation ?? 'native')) return false
      if (snapshot.id !== view.id || snapshot.imageLayerId !== (view.composite?.mode === 'crossfade' ? view.composite.imageLayerId : null) || snapshot.warpKind !== (view.imagePlaneWarp?.kind ?? null)) return false
      for (let i = 0; i < 11; i++) if (!Object.is(values[i + 15], i < 2 ? view.imagePlaneWarp?.unwarpedViewportPixels[i] ?? NaN : view.imagePlaneWarp?.renderToSourcePixels[i - 2] ?? NaN)) return false
      for (let i = 0; i < 3; i++) if (values[i] !== view.camera.positionMetres[i]) return false
      for (let i = 0; i < 4; i++) if (values[i + 3] !== view.camera.quaternion[i]) return false
      if (values[7] !== view.camera.verticalFovDegrees || !Object.is(values[8], view.camera.principalPointViewportPixels?.[0] ?? NaN)
        || !Object.is(values[9], view.camera.principalPointViewportPixels?.[1] ?? NaN)) return false
      for (let i = 0; i < 4; i++) if (values[i + 10] !== view.rectSourcePixels[i]) return false
      if (values[14] !== (view.composite?.mode === 'crossfade' ? view.composite.opacity : 1)) return false
    }
    return true
  }

  function finishCaptures() {
    renderedProbeRevision = probe?.status === 'active' ? probeInternals.get(probe)!.revision.value : -1
    renderedVisibilityRevision = visibilityProbe?.status === 'active' ? partVisibilityInternals.get(visibilityProbe)!.revision.value : -1
    frameWidth = canvas.clientWidth
    frameHeight = canvas.clientHeight
    frameFov = camera.fov
    frameAspect = camera.aspect
    frameCameraPosition.copy(camera.position)
    frameCameraQuaternion.copy(camera.quaternion)
    frameCameraProjection.copy(camera.projectionMatrix)
  }

  function render() {
    if (disposed) throw new Error('Viewer is disposed.')
    if (mode === 'exploring') controls.update()
    drawEpoch++
    renderedViews = null
    activeView = null
    activeViewIndex = -1
    capturedViewOrder.length = 0
    beginFrame()
    camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
    camera.updateProjectionMatrix()
    drawView(FULL_FRAME, 'native', null, mirrorTarget, false)
    diagnosticDraw = true
    captureView(EXPLORING_VIEW_ID, FULL_FRAME, 'native', null, 1)
    capturePartVisibility(EXPLORING_VIEW_ID, FULL_FRAME, 'native', null, 1)
    diagnosticDraw = false
    finishCaptures()
    renderer.setScissorTest(false)
  }

  function assertTargetCapacity(width: number, height: number, label: string, viewId?: string) {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width < 1 || height < 1
      || width > renderer.capabilities.maxTextureSize || height > renderer.capabilities.maxTextureSize
      || width > maxRenderbufferSize || height > maxRenderbufferSize
      || width > maxViewportDimensions[0]! || height > maxViewportDimensions[1]!) {
      throw new ViewCapacityError(`${label}${viewId ? ` for view "${viewId}"` : ''} ${width}×${height}px exceeds GPU limits (texture ${renderer.capabilities.maxTextureSize}px, renderbuffer ${maxRenderbufferSize}px, viewport ${maxViewportDimensions[0]}×${maxViewportDimensions[1]}px).`)
    }
  }

  function preflightViews(views: readonly SourceView[]) {
    if (disposed) throw new Error('Viewer is disposed.')
    // Every destination/diagnostic/composite target is the actual full backing
    // store, not merely the source gate. All stages have depth attachments.
    assertTargetCapacity(gl.drawingBufferWidth, gl.drawingBufferHeight, 'Full destination')
    const ratio = renderer.getPixelRatio()
    assertTargetCapacity(Math.max(1, Math.round(gate.width * ratio)), Math.max(1, Math.round(gate.height * ratio)), 'Native mirror viewport')
    for (let i = 0; i < views.length; i++) {
      const view = views[i]!, rect = view.rectSourcePixels, grid = view.imagePlaneWarp?.unwarpedViewportPixels
      if (grid) assertTargetCapacity(Math.ceil(grid[0]), Math.ceil(grid[1]), 'Native warp viewport', view.id)
      // The viewport is independently rounded by three.js; a subpixel source
      // ROI may legitimately have no raster support and is not an allocation.
      const width = Math.round(rect[2] / SOURCE_WIDTH * gate.width * ratio)
      const height = Math.round(rect[3] / SOURCE_HEIGHT * gate.height * ratio)
      if (!Number.isFinite(width) || !Number.isFinite(height) || width < 0 || height < 0
        || width > maxViewportDimensions[0]! || height > maxViewportDimensions[1]!) {
        throw new ViewCapacityError(`Source destination viewport for view "${view.id}" ${width}×${height}px exceeds GPU viewport capacity ${maxViewportDimensions[0]}×${maxViewportDimensions[1]}px.`)
      }
      for (let j = 0; j < i; j++) if (views[j]!.id === view.id) throw new Error(`Simultaneous source view IDs must be unique: "${view.id}".`)
    }
  }

  function renderViews(views: readonly SourceView[], beforeView: ((view: SourceView, index: number) => void) | undefined, timeSeconds: number) {
    preflightViews(views)
    assertSourceCompositeWeights(views)
    drawEpoch++
    renderedViews = views
    capturedViewOrder.length = probe || visibilityProbe ? views.length : 0
    beginFrame()
    for (let i = 0; i < views.length;) {
      const first = views[i]!
      const group = first.composite?.mode === 'crossfade' ? first.composite.groupId : null
      if (group !== null) {
        ensureCompositeTargets()
        renderer.getClearColor(savedClearColor)
        const alpha = renderer.getClearAlpha()
        renderer.setRenderTarget(compositeSumTarget)
        renderer.setScissorTest(false)
        renderer.setClearColor(0x000000, 0)
        renderer.clear(true, false, false)
        renderer.setClearColor(savedClearColor, alpha)
      }
      do {
        activeView = views[i]!
        activeViewIndex = i
        const view = views[i]!
        const member = view.composite
        if (group !== null && (member?.mode !== 'crossfade' || member.groupId !== group)) break
        const opacity = member?.mode === 'crossfade' ? member.opacity : 1
        const rect = view.rectSourcePixels
        const presentation = view.presentation ?? 'native'
        beforeView?.(view, i)
        const grid = view.imagePlaneWarp?.unwarpedViewportPixels
        writeCamera(camera, view.camera, grid?.[0] ?? rect[2], grid?.[1] ?? rect[3])
        snapshotView(view)
        if (probe || visibilityProbe) capturedViewOrder[i] = view
        const previous = i > 0 ? views[i - 1]!.composite : undefined
        if (group !== null && member?.mode === 'crossfade' && (previous?.mode !== 'crossfade' || previous.groupId !== group || previous.imageLayerId !== member.imageLayerId)) {
          renderer.getClearColor(savedClearColor)
          const alpha = renderer.getClearAlpha()
          renderer.setRenderTarget(compositeImageTarget)
          renderer.setScissorTest(false)
          renderer.setClearColor(0x000000, 0)
          renderer.clear(true, true, false)
          renderer.setClearColor(savedClearColor, alpha)
        }
        if (opacity > 0) {
          drawView(rect, presentation, group === null ? null : compositeImageTarget, mirrorTarget, true)
          const next = views[i + 1]?.composite
          if (group !== null && member?.mode === 'crossfade' && (next?.mode !== 'crossfade' || next.groupId !== group || next.imageLayerId !== member.imageLayerId)) {
            compositeMaterial.uniforms.stage!.value = 0
            compositeMaterial.uniforms.weight!.value = opacity
            compositeMaterial.blending = THREE.CustomBlending
            compositeMaterial.blendEquation = THREE.AddEquation
            compositeMaterial.blendSrc = THREE.OneFactor
            compositeMaterial.blendDst = THREE.OneFactor
            compositeMaterial.blendEquationAlpha = THREE.AddEquation
            compositeMaterial.blendSrcAlpha = THREE.OneFactor
            compositeMaterial.blendDstAlpha = THREE.OneFactor
            compositeBlit(FULL_FRAME, compositeSumTarget, compositeImageTarget!)
          }
        }
        // Higher subviews of this same image mask every diagnostic raster too.
        diagnosticDraw = true
        captureView(view.id, rect, presentation, timeSeconds, opacity)
        capturePartVisibility(view.id, rect, presentation, timeSeconds, opacity)
        diagnosticDraw = false
        i++
        if (group === null) break
      } while (i < views.length)
      if (group !== null) {
        compositeMaterial.uniforms.stage!.value = 1
        compositeBackground.copy(scene.background instanceof THREE.Color ? scene.background : savedClearColor).convertLinearToSRGB()
        compositeMaterial.blending = THREE.NoBlending
        compositeBlit(FULL_FRAME, null, compositeSumTarget!)
        renderer.clear(false, true, false)
      }
    }
    finishCaptures()
    renderer.setRenderTarget(null)
    renderer.setScissorTest(false)
  }

  const probeTargetOptions = { depthBuffer: false, stencilBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, generateMipmaps: false, type: THREE.UnsignedByteType }
  function ensureProbeTargets() {
    // Actual drawing-buffer size, not the renderer's cached logical size.
    const width = gl.drawingBufferWidth
    const height = gl.drawingBufferHeight
    if (!probeTarget) probeTarget = new THREE.WebGLRenderTarget(width, height, probeTargetOptions)
    else if (probeTarget.width !== width || probeTarget.height !== height) probeTarget.setSize(width, height)
    if (!probeMirrorTarget) probeMirrorTarget = new THREE.WebGLRenderTarget(mirrorTarget.width, mirrorTarget.height, probeTargetOptions)
    else if (probeMirrorTarget.width !== mirrorTarget.width || probeMirrorTarget.height !== mirrorTarget.height) probeMirrorTarget.setSize(mirrorTarget.width, mirrorTarget.height)
  }

  /** Read one pass over [x0,x1)×[y0,y1) backing pixels and accumulate per-bit centroids. */
  function readPass(target: THREE.WebGLRenderTarget, x0: number, y0: number, x1: number, y1: number) {
    for (let bit = 0; bit < SLOTS_PER_PASS; bit++) {
      const o = bit * ACCUMULATOR_STRIDE
      accumulators[o] = 0; accumulators[o + 1] = 0; accumulators[o + 2] = 0
      accumulators[o + 3] = Infinity; accumulators[o + 4] = -Infinity
      accumulators[o + 5] = Infinity; accumulators[o + 6] = -Infinity
    }
    const width = x1 - x0
    const height = y1 - y0
    if (width <= 0 || height <= 0) return
    const count = width * height
    if (readbackWords.length < count) {
      readback = new Uint8Array(count * 4)
      readbackWords = new Uint32Array(readback.buffer)
    }
    readbackWords.fill(0, 0, count)
    renderer.readRenderTargetPixels(target, x0, y0, width, height, readback)
    for (let i = 0; i < count; i++) {
      if (readbackWords[i] === 0) continue
      const px = x0 + (i % width) + 0.5
      const py = y0 + Math.floor(i / width) + 0.5
      for (let channel = 0; channel < 4; channel++) {
        let byte = readback[i * 4 + channel]!
        while (byte !== 0) {
          const low = byte & -byte
          byte ^= low
          const o = (channel * 8 + 31 - Math.clz32(low)) * ACCUMULATOR_STRIDE
          accumulators[o]! += 1
          accumulators[o + 1]! += px
          accumulators[o + 2]! += py
          if (px < accumulators[o + 3]!) accumulators[o + 3] = px
          if (px > accumulators[o + 4]!) accumulators[o + 4] = px
          if (py < accumulators[o + 5]!) accumulators[o + 5] = py
          if (py > accumulators[o + 6]!) accumulators[o + 6] = py
        }
      }
    }
  }

  function nativelyHidden(object: THREE.Object3D): boolean {
    for (let node: THREE.Object3D | null = object; node; node = node.parent) if (!node.visible) return true
    return false
  }

  function captureView(viewId: string, rect: readonly [number, number, number, number], presentation: Presentation, timeSeconds: number | null, sourceOpacity: number) {
    const internals = probe?.status === 'active' ? probeInternals.get(probe) : undefined
    if (!internals) return
    const markers = internals.markers
    let capture = captures.get(viewId)
    if (!capture) {
      capture = { epoch: -1, presentation, timeSeconds, sourceOpacity, states: new Uint8Array(markers.length), values: new Float64Array(markers.length * 5), sourceUncertainties: new Float64Array(markers.length), reasons: new Array<string | null>(markers.length).fill(null), worldValues: new Float64Array(markers.length * 3), worldReasons: new Array<string | null>(markers.length).fill(null) }
      captures.set(viewId, capture)
    }
    capture.epoch = drawEpoch
    capture.presentation = presentation
    capture.timeSeconds = timeSeconds
    capture.sourceOpacity = sourceOpacity
    // This follows the existing native draw, before any diagnostic pass or next
    // view's pose update. Snapshot the actual float32 vertex, not the anchor
    // catalogue/rest pose or a CPU inverse projection of raster coordinates.
    for (let i = 0; i < markers.length; i++) {
      const marker = markers[i]!
      const object = marker.object
      let reason = marker.reason
      if (object) {
        if (sourceOpacity === 0) reason = 'view has zero measured source opacity; no native draw to bind world coordinates'
        else if (object.geometry.hasAttribute('springCoordinate')) reason = 'marker uses GPU spring deformation; matrixWorld alone does not locate its vertex'
        else {
          for (let node: THREE.Object3D | null = object; node; node = node.parent) {
            if (node.matrixWorldNeedsUpdate) {
              reason = 'marker or ancestor world matrix is not current at the native draw'
              break
            }
          }
          if (reason === null) {
            const position = object.geometry.getAttribute('position')
            const x = position.getX(0), y = position.getY(0), z = position.getZ(0)
            const e = object.matrixWorld.elements
            const w = e[3]! * x + e[7]! * y + e[11]! * z + e[15]!
            const o = i * 3
            capture.worldValues[o] = (e[0]! * x + e[4]! * y + e[8]! * z + e[12]!) / w
            capture.worldValues[o + 1] = (e[1]! * x + e[5]! * y + e[9]! * z + e[13]!) / w
            capture.worldValues[o + 2] = (e[2]! * x + e[6]! * y + e[10]! * z + e[14]!) / w
            if (!Number.isFinite(capture.worldValues[o]) || !Number.isFinite(capture.worldValues[o + 1]) || !Number.isFinite(capture.worldValues[o + 2])) {
              reason = 'marker world transform did not yield three finite metres'
            }
          }
        }
      }
      capture.worldReasons[i] = reason ?? (object ? null : 'native marker is unresolved')
    }
    if (sourceOpacity === 0) {
      for (let i = 0; i < markers.length; i++) {
        capture.states[i] = markers[i]!.slot < 0 ? 1 : 2
        capture.reasons[i] = markers[i]!.slot < 0 ? markers[i]!.reason : 'view has zero measured source opacity'
      }
      return
    }
    for (let i = 0; i < markers.length; i++) {
      capture.states[i] = 1
      capture.reasons[i] = markers[i]!.slot < 0 ? markers[i]!.reason : 'GPU capture did not reach this marker'
    }
    if (internals.passes === 0) return
    ensureProbeTargets()
    const target = probeTarget!
    const mirrorStage = probeMirrorTarget!
    const savedBackground = scene.background
    const savedLayers = camera.layers.mask
    renderer.getClearColor(savedClearColor)
    const savedClearAlpha = renderer.getClearAlpha()
    scene.background = null
    renderer.setClearColor(0x000000, 0)
    try {
      // The final stage's actual GL viewport for this view, in backing pixels.
      renderer.setRenderTarget(target)
      renderer.setScissorTest(true)
      viewport(rect[0], rect[1], rect[2], rect[3])
      renderer.getCurrentViewport(probeViewport)
      const x0 = Math.max(0, probeViewport.x, viewScissorPixels.x)
      const y0 = Math.max(0, probeViewport.y, viewScissorPixels.y)
      const x1 = Math.min(target.width, probeViewport.x + probeViewport.z, viewScissorPixels.x + viewScissorPixels.z)
      const y1 = Math.min(target.height, probeViewport.y + probeViewport.w, viewScissorPixels.y + viewScissorPixels.w)
      renderer.clear(true, false, false)
      renderer.render(referenceScene, mirrorCamera)
      readPass(target, x0, y0, x1, y1)
      if (accumulators[0] === 0 || accumulators[ACCUMULATOR_STRIDE] === 0) {
        markAll(capture, markers, 'view reference markers were not rendered; viewport mapping unmeasured')
        return
      }
      const ax = accumulators[1]! / accumulators[0]!
      const ay = accumulators[2]! / accumulators[0]!
      const bx = accumulators[ACCUMULATOR_STRIDE + 1]! / accumulators[ACCUMULATOR_STRIDE]!
      const by = accumulators[ACCUMULATOR_STRIDE + 2]! / accumulators[ACCUMULATOR_STRIDE]!
      // Reference centroids are independent verification, never the mapping
      // authority. A boundary point can land in either adjacent cell; even
      // coincident centroids in a one-pixel viewport are valid witnesses.
      const referenceTolerance = 8 * Number.EPSILON * Math.max(target.width, target.height, 1)
      if (Math.abs(ax - (probeViewport.x + REFERENCE_SOURCE_LOW * probeViewport.z)) > 0.5 + referenceTolerance
        || Math.abs(bx - (probeViewport.x + (1 - REFERENCE_SOURCE_LOW) * probeViewport.z)) > 0.5 + referenceTolerance
        || Math.abs(ay - (probeViewport.y + (1 - REFERENCE_SOURCE_LOW) * probeViewport.w)) > 0.5 + referenceTolerance
        || Math.abs(by - (probeViewport.y + REFERENCE_SOURCE_LOW * probeViewport.w)) > 0.5 + referenceTolerance
        || bx < ax || by > ay) {
        markAll(capture, markers, 'view reference cells disagree with actual GL viewport or axis orientation')
        return
      }
      const cssX = canvas.clientWidth / gl.drawingBufferWidth
      const cssY = canvas.clientHeight / gl.drawingBufferHeight
      const sourcePerPixelX = cssX * SOURCE_WIDTH / gate.width
      const sourcePerPixelY = cssY * SOURCE_HEIGHT / gate.height
      // Ordinary cameras use the real rounded GL viewport; source pixel cells
      // use the continuous source gate. Bound their affine discrepancy at both
      // viewport endpoints, including subjects outside the reference pair.
      let viewportQuantizationX = 0
      let viewportQuantizationY = 0
      if (!activeView?.imagePlaneWarp) {
        const leftError = probeViewport.x * sourcePerPixelX - gate.x * SOURCE_WIDTH / gate.width - rect[0]
        const topError = (gl.drawingBufferHeight - probeViewport.y - probeViewport.w) * sourcePerPixelY - gate.y * SOURCE_HEIGHT / gate.height - rect[1]
        viewportQuantizationX = Math.max(Math.abs(leftError), Math.abs(leftError + probeViewport.z * sourcePerPixelX - rect[2])) / sourcePerPixelX
        viewportQuantizationY = Math.max(Math.abs(topError), Math.abs(topError + probeViewport.w * sourcePerPixelY - rect[3])) / sourcePerPixelY
      }
      const mirror = presentation === 'horizontal-mirror' && !activeView?.imagePlaneWarp
      const ratioX = mirror ? mirrorStage.width / probeViewport.z : 1
      const ratioY = mirror ? mirrorStage.height / probeViewport.w : 1
      // Nearest-sampled through the real blit, a marker must span at least one
      // destination sample; an odd square keeps its centre on the anchor.
      const pointSize = mirror ? 2 * Math.ceil(Math.max(ratioX, ratioY, 1) / 2) + 1 : 1
      const warped = !!activeView?.imagePlaneWarp
      const nativeCellUncertainty = warpQuantization()
      const homography = activeView?.imagePlaneWarp?.renderToSourcePixels
      // Validation above already excludes singular transforms. Only exact
      // separable affine cells form a Cartesian product of destination samples
      // with a mean within half a destination cell of the native-cell midpoint.
      // Oblique/projective cells can alias to one edge even without clipping.
      const separableWarp = homography !== undefined && homography[6] === 0 && homography[7] === 0
        && ((homography[1] === 0 && homography[3] === 0) || (homography[0] === 0 && homography[4] === 0))
      // Two samples in one native texel differ by at most twice its
      // half-cell Jacobian bound; a mirrored square has the given full span.
      const footprintWidth = mirror ? pointSize / ratioX * sourcePerPixelX : 2 * nativeCellUncertainty
      const footprintHeight = mirror ? pointSize / ratioY * sourcePerPixelY : 2 * nativeCellUncertainty
      if (pointSize > maxPointSize) {
        markAll(capture, markers, `mirror downscale needs ${pointSize}px GPU points; device maximum is ${maxPointSize}px`)
        return
      }
      camera.layers.set(PROBE_LAYER)
      internals.pointSize.value = pointSize
      for (let pass = 0; pass < internals.passes; pass++) {
        internals.pass.value = pass
        drawView(rect, presentation, target, mirrorStage, true)
        readPass(target, x0, y0, x1, y1)
        for (let i = 0; i < markers.length; i++) {
          const marker = markers[i]!
          if (marker.slot < 0 || Math.floor(marker.slot / SLOTS_PER_PASS) !== pass) continue
          const o = (marker.slot % SLOTS_PER_PASS) * ACCUMULATOR_STRIDE
          const count = accumulators[o]!
          if (count === 0) {
            capture.states[i] = 2
            capture.reasons[i] = nativelyHidden(marker.object!) ? 'native part or ancestor hidden in this view'
              : 'no marker pixels: clipped by camera frustum, near/far planes or view scissor'
            continue
          }
          const px = accumulators[o + 1]! / count
          const py = accumulators[o + 2]! / count
          let uncertaintyX = 0.5 + viewportQuantizationX
          let uncertaintyY = 0.5 + viewportQuantizationY
          let warpUncertainty = nativeCellUncertainty
          if (mirror || warped) {
            const clippedX = accumulators[o + 3]! - 0.5 <= x0 || accumulators[o + 4]! + 0.5 >= x1
            const clippedY = accumulators[o + 5]! - 0.5 <= y0 || accumulators[o + 6]! + 0.5 >= y1
            // Surviving GPU cells plus a full footprint span enclose every
            // possibly omitted sample. Test the real later same-image masks;
            // no CPU-projected landmark is used to infer the missing pixels.
            const masked = activeView?.composite?.mode === 'crossfade' && higherMaskIntersects(
              ((accumulators[o + 3]! - 0.5) * cssX - gate.x) * SOURCE_WIDTH / gate.width - footprintWidth,
              ((gl.drawingBufferHeight - accumulators[o + 6]! - 0.5) * cssY - gate.y) * SOURCE_HEIGHT / gate.height - footprintHeight,
              ((accumulators[o + 4]! + 0.5) * cssX - gate.x) * SOURCE_WIDTH / gate.width + footprintWidth,
              ((gl.drawingBufferHeight - accumulators[o + 5]! + 0.5) * cssY - gate.y) * SOURCE_HEIGHT / gate.height + footprintHeight,
            )
            if (mirror) {
              uncertaintyX += 0.5 / ratioX
              uncertaintyY += 0.5 / ratioY
              if (clippedX || masked) uncertaintyX += pointSize / (2 * ratioX)
              if (clippedY || masked) uncertaintyY += pointSize / (2 * ratioY)
            } else if (!separableWarp || clippedX || clippedY || masked) {
              // Without the uncut separable-cell mean guarantee, the feature
              // and observed mean can differ by the native cell's full diameter.
              warpUncertainty += nativeCellUncertainty
            }
          }
          const v = i * 5
          capture.states[i] = 0
          capture.reasons[i] = null
          capture.values[v] = px * cssX
          capture.values[v + 1] = (gl.drawingBufferHeight - py) * cssY
          capture.values[v + 2] = (px * cssX - gate.x) * SOURCE_WIDTH / gate.width
          capture.values[v + 3] = ((gl.drawingBufferHeight - py) * cssY - gate.y) * SOURCE_HEIGHT / gate.height
          capture.sourceUncertainties[i] = Math.hypot(uncertaintyX * sourcePerPixelX, uncertaintyY * sourcePerPixelY) + warpUncertainty
          capture.values[v + 4] = Math.max(uncertaintyX * cssX, uncertaintyY * cssY) + warpUncertainty * Math.max(gate.width / SOURCE_WIDTH, gate.height / SOURCE_HEIGHT)
        }
      }
    } finally {
      internals.pass.value = 0
      camera.layers.mask = savedLayers
      scene.background = savedBackground
      renderer.setClearColor(savedClearColor, savedClearAlpha)
      renderer.setRenderTarget(null)
      renderer.setScissorTest(true)
    }
  }

  function markAll(capture: ViewCapture, markers: readonly ProbeMarker[], reason: string) {
    for (let i = 0; i < markers.length; i++) if (markers[i]!.slot >= 0) capture.reasons[i] = reason
  }

  function releaseProbeTargets() {
    probeTarget?.dispose()
    probeMirrorTarget?.dispose()
    probeTarget = null
    probeMirrorTarget = null
    readback = new Uint8Array(0)
    readbackWords = new Uint32Array(0)
    captures.clear()
  }

  function setLandmarkProbe(next: LandmarkProbe | null) {
    if (next === probe) return
    if (next && !probeInternals.has(next)) throw new Error('Landmark probe was not created by Machine.createLandmarkProbe or is disposed.')
    probe?.dispose()
    probe = next
    captures.clear()
    if (!next) releaseProbeTargets()
  }

  function readRenderedLandmarks(viewId: string): RenderedLandmarks | null {
    const internals = probe?.status === 'active' ? probeInternals.get(probe) : undefined
    const capture = captures.get(viewId)
    if (!internals || !capture || capture.epoch !== drawEpoch || internals.revision.value !== renderedProbeRevision || disposed || !capturesFresh()) return null
    return {
      method: 'gpu-readback', visibilityMode: 'depth-off-landmark-projection', status: 'captured', sourceOpacity: capture.sourceOpacity,
      ...capturedSupport(viewId),
      viewId, presentation: capture.presentation, timeSeconds: capture.timeSeconds,
      landmarks: internals.markers.map((marker, i) => {
        const rendered = capture.states[i] === 0
        const v = i * 5
        return {
          id: marker.id,
          state: CAPTURE_STATES[capture.states[i]!]!,
          worldMetres: capture.worldReasons[i] === null ? [capture.worldValues[i * 3]!, capture.worldValues[i * 3 + 1]!, capture.worldValues[i * 3 + 2]!] : null,
          worldReason: capture.worldReasons[i]!,
          canvasPixels: rendered ? [capture.values[v]!, capture.values[v + 1]!] : null,
          sourcePixels: rendered ? [capture.values[v + 2]!, capture.values[v + 3]!] : null,
          uncertaintyCanvasPixels: rendered ? capture.values[v + 4]! : null,
          uncertaintySourcePixels: rendered ? capture.sourceUncertainties[i]! : null,
          reason: capture.reasons[i]!,
        }
      }),
    }
  }

  function ensureVisibilityTargets() {
    const width = gl.drawingBufferWidth
    const height = gl.drawingBufferHeight
    if (!visibilityTarget) visibilityTarget = new THREE.WebGLRenderTarget(width, height, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter })
    else if (visibilityTarget.width !== width || visibilityTarget.height !== height) visibilityTarget.setSize(width, height)
    if (!visibilityMirrorTarget) visibilityMirrorTarget = new THREE.WebGLRenderTarget(mirrorTarget.width, mirrorTarget.height, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter })
    else if (visibilityMirrorTarget.width !== mirrorTarget.width || visibilityMirrorTarget.height !== mirrorTarget.height) visibilityMirrorTarget.setSize(mirrorTarget.width, mirrorTarget.height)
  }

  function capturePartVisibility(viewId: string, rect: readonly [number, number, number, number], presentation: Presentation, timeSeconds: number | null, sourceOpacity: number) {
    const internals = visibilityProbe?.status === 'active' ? partVisibilityInternals.get(visibilityProbe) : undefined
    if (!internals) return
    internals.synchronize()
    const entries = internals.entries
    let capture = visibilityCaptures.get(viewId)
    if (!capture || capture.values.length !== entries.length * 5) {
      capture = { epoch: -1, inventoryRevision: -1, presentation, timeSeconds, sourceOpacity, rect: [rect[0], rect[1], rect[2], rect[3]], cameraValues: new Float64Array(10), values: new Float64Array(entries.length * 5), contourCounts: new Uint32Array(entries.length), contourSampleCounts: new Uint16Array(entries.length), contourOffsets: new Uint32Array(entries.length), contourSamples: new Float64Array(0), uncertaintySourcePixels: 0 }
      visibilityCaptures.set(viewId, capture)
    }
    capture.epoch = drawEpoch
    capture.inventoryRevision = internals.inventoryRevision.value
    capture.presentation = presentation
    capture.timeSeconds = timeSeconds
    capture.sourceOpacity = sourceOpacity
    capture.contourCounts.fill(0)
    capture.contourSampleCounts.fill(0)
    capture.uncertaintySourcePixels = 0
    for (let axis = 0; axis < 4; axis++) capture.rect[axis] = rect[axis]!
    camera.position.toArray(capture.cameraValues, 0)
    camera.quaternion.toArray(capture.cameraValues, 3)
    capture.cameraValues[7] = camera.fov
    capture.cameraValues[8] = (activeView?.imagePlaneWarp?.unwarpedViewportPixels[0] ?? rect[2]) / 2 - (camera.view?.enabled ? camera.view.offsetX : 0)
    capture.cameraValues[9] = (activeView?.imagePlaneWarp?.unwarpedViewportPixels[1] ?? rect[3]) / 2 - (camera.view?.enabled ? camera.view.offsetY : 0)
    for (let i = 0; i < entries.length; i++) {
      const o = i * 5
      capture.values[o] = 0
      capture.values[o + 1] = Infinity; capture.values[o + 2] = Infinity
      capture.values[o + 3] = -Infinity; capture.values[o + 4] = -Infinity
    }
    if (sourceOpacity === 0 || entries.length === 0) return
    ensureVisibilityTargets()
    const target = visibilityTarget!
    const stage = visibilityMirrorTarget!
    const background = scene.background
    const layers = camera.layers.mask
    renderer.getClearColor(savedClearColor)
    const alpha = renderer.getClearAlpha()
    scene.background = null
    renderer.setClearColor(0x000000, 0)
    // No substitute meshes: render the very same native objects, geometry,
    // transforms, shader deformation, alpha/clipping and material-side rules.
    for (const entry of entries) entry.object.material = entry.diagnostic
    try {
      camera.layers.disable(PROBE_LAYER)
      drawView(rect, presentation, target, stage, true)
      renderer.getCurrentViewport(probeViewport)
      const x0 = Math.max(0, probeViewport.x, viewScissorPixels.x)
      const y0 = Math.max(0, probeViewport.y, viewScissorPixels.y)
      const x1 = Math.min(target.width, probeViewport.x + probeViewport.z, viewScissorPixels.x + viewScissorPixels.z)
      const y1 = Math.min(target.height, probeViewport.y + probeViewport.w, viewScissorPixels.y + viewScissorPixels.w)
      const width = x1 - x0
      const height = y1 - y0
      if (width <= 0 || height <= 0) return
      const bytes = width * height * 4
      if (visibilityPixels.length < bytes) visibilityPixels = new Uint8Array(bytes)
      renderer.readRenderTargetPixels(target, x0, y0, width, height, visibilityPixels)
      if (contourOrdinals.length < entries.length) contourOrdinals = new Uint32Array(entries.length)
      contourOrdinals.fill(0, 0, entries.length)
      const pixelCount = width * height
      if (contourFlags.length < pixelCount) contourFlags = new Uint8Array(pixelCount)
      contourFlags.fill(0, 0, pixelCount)
      const sourcePerPixelX = SOURCE_WIDTH / gate.width * canvas.clientWidth / target.width
      const sourcePerPixelY = SOURCE_HEIGHT / gate.height * canvas.clientHeight / target.height
      const nativeHalfCell = warpQuantization()
        + (presentation === 'horizontal-mirror' && !activeView?.imagePlaneWarp
          ? Math.hypot(probeViewport.z * sourcePerPixelX / stage.width, probeViewport.w * sourcePerPixelY / stage.height) / 2 : 0)
      const nativeRadius = nativeHalfCell + viewportSourceDiscrepancy(rect, sourcePerPixelX, sourcePerPixelY)
      // Differing neighbouring native surface samples bracket an ID boundary.
      // Their warped centres are within Q of the final cells, so Q + Dmax
      // bounds the boundary distance (and the exclusive cell-corner distance).
      capture.uncertaintySourcePixels = Math.max(sourcePerPixelX, sourcePerPixelY) + nativeRadius
      for (let i = 0; i < width * height; i++) {
        const pixel = i * 4
        const id = visibilityPixels[pixel]! + visibilityPixels[pixel + 1]! * 256 + visibilityPixels[pixel + 2]! * 65536
        if (id === 0 || id > entries.length) continue
        const o = (id - 1) * 5
        const left = x0 + i % width
        const top = target.height - 1 - (y0 + Math.floor(i / width))
        capture.values[o]!++
        if (left < capture.values[o + 1]!) capture.values[o + 1] = left
        if (top < capture.values[o + 2]!) capture.values[o + 2] = top
        if (left + 1 > capture.values[o + 3]!) capture.values[o + 3] = left + 1
        if (top + 1 > capture.values[o + 4]!) capture.values[o + 4] = top + 1
        if (nativeContourPixel(i, id, width, pixelCount, entries)) {
          const sx = ((left + 0.5) * canvas.clientWidth / target.width - gate.x) * SOURCE_WIDTH / gate.width
          const sy = ((top + 0.5) * canvas.clientHeight / target.height - gate.y) * SOURCE_HEIGHT / gate.height
          // All adjacent final centres and their native-centre offsets lie in
          // this box. Require its complete convex footprint, not sparse
          // endpoints alone, to remain inside support and outside later masks.
          if (sourceRegionUnmasked(sx - sourcePerPixelX - nativeRadius, sy - sourcePerPixelY - nativeRadius,
            sx + sourcePerPixelX + nativeRadius, sy + sourcePerPixelY + nativeRadius)) {
            capture.contourCounts[id - 1]!++
            contourFlags[i] = 1
          }
        }
      }
      let sampleTotal = 0
      for (let path = 0; path < entries.length; path++) {
        capture.contourOffsets[path] = sampleTotal
        sampleTotal += Math.min(capture.contourCounts[path]!, RASTER_SAMPLE_LIMIT)
      }
      if (capture.contourSamples.length < sampleTotal * 2) capture.contourSamples = new Float64Array(sampleTotal * 2)
      // Sampling is a subset of actual ID-boundary centres from this same
      // readback, never rectangle corners or a reconstructed silhouette.
      for (let pixel = 0; pixel < pixelCount; pixel++) {
        if (contourFlags[pixel] !== 1) continue
        const path = nativePixelId(pixel) - 1
        const ordinal = contourOrdinals[path]!++
        const sample = capture.contourSampleCounts[path]!
        const count = capture.contourCounts[path]!
        const limit = Math.min(count, RASTER_SAMPLE_LIMIT)
        if (sample >= limit || ordinal !== (limit === 1 ? 0 : Math.floor(sample * (count - 1) / (limit - 1)))) continue
        const o = (capture.contourOffsets[path]! + sample) * 2
        capture.contourSamples[o] = x0 + pixel % width + 0.5
        capture.contourSamples[o + 1] = target.height - (y0 + Math.floor(pixel / width) + 0.5)
        capture.contourSampleCounts[path] = sample + 1
      }
    } finally {
      for (const entry of entries) entry.object.material = entry.original
      camera.layers.mask = layers
      scene.background = background
      renderer.setClearColor(savedClearColor, alpha)
      renderer.setRenderTarget(null)
      renderer.setScissorTest(true)
    }
  }
  function nativePixelId(pixel: number): number {
    const offset = pixel * 4
    return visibilityPixels[offset]! + visibilityPixels[offset + 1]! * 256 + visibilityPixels[offset + 2]! * 65536
  }

  function nativeContourPixel(pixel: number, id: number, width: number, count: number, entries: readonly NativeDrawable[]): boolean {
    const x = pixel % width
    if (!(entries[id - 1]?.object instanceof THREE.Mesh) || x === 0 || x === width - 1 || pixel < width || pixel >= count - width) return false
    // A sprite/line ID is not evidence of a triangle-surface boundary.
    return meshBoundaryNeighbor(pixel - 1, id, entries) || meshBoundaryNeighbor(pixel + 1, id, entries)
      || meshBoundaryNeighbor(pixel - width, id, entries) || meshBoundaryNeighbor(pixel + width, id, entries)
  }

  function meshBoundaryNeighbor(pixel: number, id: number, entries: readonly NativeDrawable[]): boolean {
    const neighbor = nativePixelId(pixel)
    return neighbor !== id && (neighbor === 0 || entries[neighbor - 1]?.object instanceof THREE.Mesh)
  }


  function setPartVisibilityProbe(next: PartVisibilityProbe | null) {
    if (next === visibilityProbe) return
    if (next && !partVisibilityInternals.has(next)) throw new Error('Part visibility probe was not created by Machine.createPartVisibilityProbe or is disposed.')
    visibilityProbe?.dispose()
    contourOrdinals = new Uint32Array(0)
    contourFlags = new Uint8Array(0)
    visibilityProbe = next
    visibilityCaptures.clear()
    renderedVisibilityRevision = -1
    if (!next) {
      visibilityTarget?.dispose(); visibilityMirrorTarget?.dispose()
      visibilityTarget = null; visibilityMirrorTarget = null
      visibilityPixels = new Uint8Array(0)
    }
  }

  function readRenderedPartVisibility(viewId: string): RenderedPartVisibility {
    const internals = visibilityProbe?.status === 'active' ? partVisibilityInternals.get(visibilityProbe) : undefined
    const capture = visibilityCaptures.get(viewId)
    const status: RenderedPartVisibility['status'] = disposed || visibilityProbe?.status === 'disposed' ? 'disposed' : !internals ? 'unavailable'
      : !capture || capture.epoch !== drawEpoch || capture.inventoryRevision !== internals.inventoryRevision.value || renderedVisibilityRevision !== internals.revision.value || !capturesFresh() ? 'stale' : 'captured'
    if (status !== 'captured' || !internals || !capture) return { method: 'gpu-readback', visibilityMode: 'depth-tested-native-surfaces', status, viewId, presentation: null, timeSeconds: null, rectSourcePixels: null, camera: null, sourceOpacity: null, resolvedImagePlaneWarp: null, sourceLayout: [], nativeViewportBackingPixels: null, destinationCellSourcePixels: [0, 0], parts: [] }
    const cssX = canvas.clientWidth / gl.drawingBufferWidth
    const cssY = canvas.clientHeight / gl.drawingBufferHeight
    const rect = capture.rect
    const left = gate.x + rect[0] / SOURCE_WIDTH * gate.width
    const top = gate.y + rect[1] / SOURCE_HEIGHT * gate.height
    return {
      method: 'gpu-readback', visibilityMode: 'depth-tested-native-surfaces', status,
      ...capturedSupport(viewId),
      viewId, presentation: capture.presentation, timeSeconds: capture.timeSeconds,
      rectSourcePixels: [...rect], sourceOpacity: capture.sourceOpacity,
      camera: {
        positionMetres: [capture.cameraValues[0]!, capture.cameraValues[1]!, capture.cameraValues[2]!],
        quaternion: [capture.cameraValues[3]!, capture.cameraValues[4]!, capture.cameraValues[5]!, capture.cameraValues[6]!],
        verticalFovDegrees: capture.cameraValues[7]!,
        principalPointViewportPixels: [capture.cameraValues[8]!, capture.cameraValues[9]!],
      },
      parts: internals.entries.map((entry, i): RenderedPartVisibility['parts'][number] => {
        const o = i * 5
        const count = capture.values[o]!
        const x0 = capture.values[o + 1]! * cssX
        const y0 = capture.values[o + 2]! * cssY
        const x1 = capture.values[o + 3]! * cssX
        const y1 = capture.values[o + 4]! * cssY
        const contour: [number, number][] = []
        for (let sample = 0; sample < capture.contourSampleCounts[i]!; sample++) {
          const s = (capture.contourOffsets[i]! + sample) * 2
          contour.push([
            rect[0] + (capture.contourSamples[s]! * cssX - left) * SOURCE_WIDTH / gate.width,
            rect[1] + (capture.contourSamples[s + 1]! * cssY - top) * SOURCE_HEIGHT / gate.height,
          ])
        }
        return {
          partPath: entry.path, status: count > 0 ? 'visible' : 'not-visible', pixelCount: count,
          canvasExtentPixels: count > 0 ? [x0, y0, x1, y1] : null,
          sourceExtentPixels: count > 0 ? [rect[0] + (x0 - left) * SOURCE_WIDTH / gate.width, rect[1] + (y0 - top) * SOURCE_HEIGHT / gate.height,
            rect[0] + (x1 - left) * SOURCE_WIDTH / gate.width, rect[1] + (y1 - top) * SOURCE_HEIGHT / gate.height] : null,
          contourSourcePixels: contour, contourPixelCount: capture.contourCounts[i]!,
          uncertaintySourcePixels: count > 0 ? capture.uncertaintySourcePixels : null,
        }
      }),
    }
  }

  function dispose() {
    if (disposed) return
    disposed = true
    drawEpoch++
    removeEventListener('resize', resize)
    controls.removeEventListener('change', onControlsChange)
    viewSnapshots.clear()
    renderedViews = null
    capturedViewOrder.length = 0
    controls.dispose()
    setLandmarkProbe(null)
    setPartVisibilityProbe(null)
    releaseProbeTargets()
    referenceGeometry.dispose(); referenceMaterial.dispose()
    mirrorTarget.dispose(); mirrorMaterial.dispose(); quadGeometry.dispose()
    warpMaterial.dispose()
    compositeImageTarget?.dispose(); compositeSumTarget?.dispose(); compositeMaterial.dispose()
    scene.environment = null
    environmentTarget.dispose()
    renderer.dispose()
  }
  resize()
  return {
    renderer, scene, camera, resize, render, preflightViews, renderViews, applyCamera, setInteraction, fitView, setLandmarkProbe, readRenderedLandmarks,
    setPartVisibilityProbe, readRenderedPartVisibility, dispose,
    get controls() { return controls },
  }
}

interface RestPart {
  path: string
  shortName: string
  node: THREE.Object3D
  position: THREE.Vector3
  quaternion: THREE.Quaternion
  scale: THREE.Vector3
  world: THREE.Matrix4
  parentInverse: THREE.Matrix4
  visible: boolean
  binding?: Binding
  station: number
  spring?: SpringDeformer
  wireLengthM?: number
  chainStationMm?: number
  chainNextStationMm?: number
  chainRestChordAngleRad?: number
  chainRestCurveM?: THREE.Vector3
  overrideWorld: THREE.Matrix4
  finalWorld: THREE.Matrix4
  overrideEpoch: number
  finalEpoch: number
}

/**
 * Missing files/names warn and remain inspectable; they never count as verified
 * fidelity. Only an identity-matched GLB is parsed and added to the shared
 * scene; a mismatched export is rejected before parsing, and a parse/binding
 * failure disposes the detached root, so Retry never stacks or leaks roots.
 */
export async function loadMachine(scene: THREE.Scene, options: LoadMachineOptions = {}): Promise<Machine> {
  const url = options.url ?? MODEL_URL
  const input = createMechanismInput()
  const pose = createMechanismPose()
  const missing: string[] = []
  const paths: string[] = []
  const parts = new Map<string, RestPart>()
  const partsByNode = new WeakMap<THREE.Object3D, RestPart>()
  let overrideEpoch = 0
  const driven: RestPart[] = []
  const overridesSeen = new Set<string>()
  const revision = { value: 0 }
  const inventoryRevision = { value: 0 }
  const nativeDrawables: Pick<NativeDrawable, 'path' | 'object'>[] = []
  const nativeDrawablePaths: string[] = []
  const nativeDrawableSeen = new WeakSet<THREE.Object3D>()
  let nativeInventoryRevision = -1
  const visibilityProbes = new Set<PartVisibilityProbe>()
  const probes = new Set<LandmarkProbe>()
  const provenance: ModelProvenance = {
    sourceCommit: MECHANISM_DATA.provenance.sourceCommit,
    sourceSha256: MECHANISM_DATA.provenance.modelSha256,
    representationKind: REPRESENTATION_KIND,
    expectedSha256: modelRepresentation.representation.sha256,
    expectedByteLength: modelRepresentation.representation.byteLength,
    observedSha256: null, observedByteLength: null, generator: null, identity: 'unavailable', url,
  }
  let availability: Machine['availability'] = 'unavailable'
  let loadError: string | null = null
  let root: THREE.Object3D | null = null
  let parsed: THREE.Object3D | null = null
  try {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Model request returned HTTP ${response.status}`)
    const buffer = await response.arrayBuffer()
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))
    provenance.observedSha256 = Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('')
    provenance.observedByteLength = buffer.byteLength
    try {
      assertModelRepresentationBytes(modelRepresentation, MECHANISM_DATA.provenance, { sha256: provenance.observedSha256, byteLength: buffer.byteLength })
      provenance.identity = 'matched'
    } catch (error) {
      provenance.identity = 'mismatched'
      availability = 'incompatible'
      loadError = error instanceof Error ? error.message : String(error)
      missing.push(loadError)
    }
    if (provenance.identity === 'matched') {
      if (!MeshoptDecoder.supported) throw new Error('This browser does not support the lossless Meshopt model decoder')
      await MeshoptDecoder.ready
      const gltf = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).parseAsync(buffer, new URL('.', new URL(url, location.href)).href)
      provenance.generator = gltf.asset.generator ?? null
      const loaded = gltf.scene
      parsed = loaded
      loaded.updateMatrixWorld(true)
      const visit = (node: THREE.Object3D, parentPath: string) => {
        const originalName = typeof node.userData.name === 'string' ? node.userData.name : node.name
        const path = parentPath ? `${parentPath}/${originalName}` : originalName
        if (node !== loaded) {
          const part: RestPart = {
            path, shortName: originalName, node, position: node.position.clone(), quaternion: node.quaternion.clone(),
            scale: node.scale.clone(), world: node.matrixWorld.clone(),
            parentInverse: node.parent!.matrixWorld.clone().invert(), visible: node.visible, station: -1,
            overrideWorld: new THREE.Matrix4(), finalWorld: new THREE.Matrix4(), overrideEpoch: -1, finalEpoch: -1,
          }
          parts.set(path, part)
          partsByNode.set(node, part)
          paths.push(path)
        }
        for (const child of node.children) visit(child, node === loaded ? '' : path)
      }
      visit(loaded, '')
      for (const binding of BINDINGS) {
        const resolved: RestPart[] = []
        for (const part of parts.values()) {
          if (!binding.pattern.test(part.path)) continue
          part.binding = binding
          part.station = binding.kind === 'indexed' ? instanceIndex(part.path, binding.pattern) - 1 : -1
          resolved.push(part)
          driven.push(part)
          if (binding.motion === 'lever-wire' || binding.motion === 'pen-wire') part.wireLengthM = nativeWireLength(part)
          if (binding.motion === 'channel-spring' || binding.motion === 'counter-spring') {
            const counter = binding.motion === 'counter-spring'
            const restLengthM = counter ? MECHANISM_DATA.counter.nativeReference.length_mm / 1000
              : MECHANISM_DATA.restChannels[part.station]!.nativeSpring.length_mm / 1000
            part.spring = createSpringDeformer(part.node, restLengthM, counter ? 'counter' : 'channel')
          }
        }
        if (resolved.length !== binding.expected) {
          missing.push(`${binding.id}: resolved ${resolved.length}/${binding.expected} (${binding.pattern})`)
        }
        if (binding.kind === 'indexed') {
          for (let station = 0; station < 20; station++) {
            if (!resolved.some(part => part.station === station)) missing.push(`${binding.id}: missing physical instance ${station + 1}`)
          }
        }
      }
      scene.add(loaded)
      root = loaded
      availability = 'available'
    }
  } catch (error) {
    if (parsed && !root) disposeNativeObject(parsed)
    parsed = null
    parts.clear()
    paths.length = 0
    driven.length = 0
    loadError = error instanceof Error ? error.message : String(error)
    availability = 'unavailable'
    missing.push(`model unavailable: ${loadError}`)
  }
  if (missing.length) console.warn(`[machine] unverified bindings/model:\n${missing.join('\n')}`)

  const a = new THREE.Vector3()
  const b = new THREE.Vector3()
  const c = new THREE.Vector3()
  const pivot = new THREE.Vector3()
  const axis = new THREE.Vector3()
  const quaternion = new THREE.Quaternion()
  const rotation = new THREE.Matrix4()
  const delta = new THREE.Matrix4()
  const swing = new THREE.Matrix4()
  const desired = new THREE.Matrix4()
  const local = new THREE.Matrix4()
  const origin = new THREE.Vector3()
  const restAnchor = new THREE.Vector3()
  const knife = new THREE.Vector3().fromArray(MECHANISM_DATA.summing.knifeMm).multiplyScalar(0.001)
  const crankPart = parts.get('harmonic-analyzer/drive-train/crankshaft-1')
  const conePart = parts.get('harmonic-analyzer/drive-train/cone-gear-shaft-1')
  const crankPivot = crankPart ? new THREE.Vector3().setFromMatrixPosition(crankPart.world) : new THREE.Vector3()
  const conePivot = conePart ? new THREE.Vector3().setFromMatrixPosition(conePart.world) : new THREE.Vector3()
  const coneAxis = conePart ? new THREE.Vector3().setFromMatrixColumn(conePart.world, 2).normalize() : new THREE.Vector3(0, 0, 1)
  const chain = MECHANISM_DATA.paperDrive.chain
  const orderedLinks = [...chain.nativeLinks].sort((left, right) => left.restStationMm - right.restStationMm)
  for (let i = 0; i < orderedLinks.length; i++) {
    const link = orderedLinks[i]!
    const part = parts.get(link.partPath)
    if (!part) continue
    part.chainStationMm = link.restStationMm
    part.chainNextStationMm = orderedLinks[(i + 1) % orderedLinks.length]!.restStationMm
    part.chainRestCurveM = new THREE.Vector3()
    chainPoint(part.chainStationMm, part.chainRestCurveM)
    chainPoint(part.chainNextStationMm, b)
    part.chainRestChordAngleRad = Math.atan2(b.y - part.chainRestCurveM.y, b.x - part.chainRestCurveM.x)
  }
  const upperSprocket = parts.get('harmonic-analyzer/paper-drive/transgear-removable-1')
  const crankSprocket = parts.get('harmonic-analyzer/paper-drive/transgear-removable-2')
  const spareSprocket = parts.get('harmonic-analyzer/paper-drive/transgear-removable-3')
  const upperMediumPath = 'harmonic-analyzer/paper-drive/transgear-removable-3@upper'
  const crankMediumPath = 'harmonic-analyzer/paper-drive/transgear-removable-3@crank'
  if (spareSprocket) {
    addPartInstance(spareSprocket.path, upperMediumPath)
    addPartInstance(spareSprocket.path, crankMediumPath)
  }
  const upperMedium = parts.get(upperMediumPath)
  const crankMedium = parts.get(crankMediumPath)

  function around(out: THREE.Matrix4, centre: THREE.Vector3, direction: THREE.Vector3, angle: number) {
    quaternion.setFromAxisAngle(direction, angle)
    out.makeRotationFromQuaternion(quaternion)
    a.copy(centre).applyMatrix4(out)
    out.setPosition(centre.x - a.x, centre.y - a.y, centre.z - a.z)
  }
  function setWorld(part: RestPart, world: THREE.Matrix4) {
    local.multiplyMatrices(part.parentInverse, world)
    local.decompose(part.node.position, part.node.quaternion, part.node.scale)
  }
  function rotate(part: RestPart, centre: THREE.Vector3, direction: THREE.Vector3, angle: number, outer?: THREE.Matrix4) {
    around(delta, centre, direction, angle)
    desired.multiplyMatrices(delta, part.world)
    if (outer) desired.premultiply(outer)
    setWorld(part, desired)
  }
  function translate(part: RestPart, x: number, y: number, z: number) {
    desired.copy(part.world)
    desired.elements[12]! += x; desired.elements[13]! += y; desired.elements[14]! += z
    setWorld(part, desired)
  }
  function endpoint(part: RestPart, restPoint: THREE.Vector3, newPoint: THREE.Vector3, angle: number) {
    // Rigid member: preserve authored rest TRS and explicitly map its actual
    // mechanical support, not the arbitrary exported Object3D origin.
    around(delta, restPoint, Z, angle)
    delta.elements[12]! += newPoint.x - restPoint.x
    delta.elements[13]! += newPoint.y - restPoint.y
    delta.elements[14]! += newPoint.z - restPoint.z
    desired.multiplyMatrices(delta, part.world)
    setWorld(part, desired)
  }
  function copyInput(source: MechanismInput) {
    if (source === input) return
    input.crankTurns = source.crankTurns
    input.amplitudes.set(source.amplitudes)
    input.phases.set(source.phases)
    input.gearing = source.gearing
    input.magnification = source.magnification
    Object.assign(input.setup, source.setup)
  }
  function warnOverride(path: string) {
    if (overridesSeen.has(path)) return
    overridesSeen.add(path)
    missing.push(`source override missing native part: ${path}`)
    console.warn(`[machine] source override missing native part: ${path}`)
  }

  function update(source: MechanismInput, overrides?: readonly PartOverride[]) {
    revision.value++
    copyInput(source)
    solveMechanism(input, pose)
    if (availability !== 'available') return
    for (const part of parts.values()) {
      part.node.position.copy(part.position)
      part.node.quaternion.copy(part.quaternion)
      part.node.scale.copy(part.scale)
      part.node.visible = part.visible
    }
    pivot.fromArray(pose.setup.coneSwingPivotM)
    around(swing, pivot, Y, pose.setup.coneSwingRad)
    for (const part of driven) {
      const j = part.station
      const p = j * 3
      switch (part.binding!.motion) {
        case 'crank': rotate(part, crankPivot, Z, pose.crankAngleRad, swing); break
        case 'cone-spin': rotate(part, conePivot, coneAxis, pose.coneShaftAngleRad, swing); break
        case 'cone-swing': desired.multiplyMatrices(swing, part.world); setWorld(part, desired); break
        case 'cylinder':
          pivot.set(MECHANISM_DATA.channel.camShaftMm[0] / 1000, MECHANISM_DATA.channel.camShaftMm[1] / 1000, part.world.elements[14]!)
          rotate(part, pivot, Z, pose.channelAnglesRad[j]!); break
        case 'rocker':
          pivot.set(MECHANISM_DATA.channel.pivotMm[0] / 1000, MECHANISM_DATA.channel.pivotMm[1] / 1000, part.world.elements[14]!)
          rotate(part, pivot, Z, pose.rockerAnglesRad[j]! - Math.atan2(-part.world.elements[1]!, -part.world.elements[0]!)); break
        case 'rod':
          restAnchor.setFromMatrixPosition(part.world)
          b.fromArray(pose.camCentersM, p)
          endpoint(part, restAnchor, b, pose.rodAnglesRad[j]! - Math.atan2(-part.world.elements[1]!, -part.world.elements[0]!)); break
        case 'bar':
          restAnchor.setFromMatrixPosition(part.world)
          b.fromArray(pose.barOriginsM, p)
          endpoint(part, restAnchor, b, pose.barAnglesRad[j]! - Math.atan2(-part.world.elements[4]!, part.world.elements[5]!)); break
        case 'lever':
          pivot.set(MECHANISM_DATA.channel.fulcrumMm[0] / 1000, MECHANISM_DATA.channel.fulcrumMm[1] / 1000, part.world.elements[14]!)
          // Remove the tiny authored rest tilt before applying solved tilt.
          rotate(part, pivot, Z, pose.leverAnglesRad[j]! - Math.atan2(-part.world.elements[1]!, -part.world.elements[0]!)); break
        case 'channel-spring':
          a.fromArray(pose.springLowerM, p); b.fromArray(pose.springUpperM, p)
          part.spring!.length.value = pose.springLengthsM[j]!
          placeSpring(part, a, b, 1); break
        case 'counter-spring':
          a.fromArray(pose.counter.lowerM); b.fromArray(pose.counter.upperM)
          part.spring!.length.value = pose.counter.lengthM
          placeSpring(part, a, b, -1); break
        case 'summing': case 'magnifier-fixed': rotate(part, knife, Z, pose.summingAngleRad); break
        case 'gooseneck': translate(part, 0, pose.counter.gooseneckHeightM - MECHANISM_DATA.counter.nativeGooseneckYMm / 1000, 0); break
        case 'magnifier-clamp': case 'magnifier-rod': case 'magnifier-fixture': {
          const change = input.magnification * MECHANISM_DATA.summing.anchorArmMm / 1000 - MECHANISM_DATA.magnifier.clampRadiusBandMm[1] / 1000
          around(delta, knife, Z, pose.summingAngleRad)
          desired.copy(part.world)
          desired.elements[12]! += change
          desired.premultiply(delta)
          if (part.binding!.motion === 'magnifier-fixture') {
            desired.elements[12]! -= Math.sin(pose.summingAngleRad) * input.setup.wireFixtureOffsetM
            desired.elements[13]! += Math.cos(pose.summingAngleRad) * input.setup.wireFixtureOffsetM
          }
          setWorld(part, desired); break
        }
        case 'wheel':
          pivot.fromArray(MECHANISM_DATA.magnifier.wheelCentreMm).multiplyScalar(0.001)
          rotate(part, pivot, Z, pose.magnifier.wheelAngleRad); break
        case 'lever-wire': alignWire(part, pose.magnifier.leverWirePathM, 3, 0); break
        case 'pen-wire': alignWire(part, pose.magnifier.penWirePathM, 3, 0); break
        case 'pen': translate(part, 0, pose.magnifier.penTravelM, 0); break
        case 'platen': translate(part, pose.platenTravelM, 0, 0); break
        case 'pinion-swing':
          pivot.fromArray(pose.setup.pinionPivotM)
          rotate(part, pivot, Z, pose.setup.pinionSwingRad); break
        case 'pinion-cam': case 'pinion-lever':
          pivot.fromArray(pose.setup.pinionLiftAxisM)
          rotate(part, pivot, Z, pose.setup.pinionCamRad); break
        case 'paper-gear': drivePaperPart(part); break
        case 'chain-link': driveChainPart(part); break
      }
    }
    driveSprockets()
    root!.updateMatrixWorld(true)
    overrideEpoch++
    if (overrides) for (const override of overrides) {
      const part = parts.get(override.partPath)
      if (!part) { warnOverride(override.partPath); continue }
      if (override.visibility) part.node.visible = override.visibility === 'visible'
      if (!override.worldPositionMetres && !override.worldQuaternion) continue
      part.node.matrixWorld.decompose(origin, quaternion, c)
      if (override.worldPositionMetres) origin.fromArray(override.worldPositionMetres)
      if (override.worldQuaternion) quaternion.fromArray(override.worldQuaternion).normalize()
      part.overrideWorld.compose(origin, quaternion, c)
      part.overrideEpoch = overrideEpoch
    }
    // Absolute source observations apply simultaneously. A child-first JSON
    // ordering must not let a later parent transform move the child's target.
    if (overrides) for (const override of overrides) {
      const part = parts.get(override.partPath)
      if (!part || part.overrideEpoch !== overrideEpoch) continue
      const parent = partsByNode.get(part.node.parent!)
      rotation.copy(parent ? finalWorld(parent) : part.node.parent!.matrixWorld).invert()
      local.multiplyMatrices(rotation, part.overrideWorld)
      local.decompose(part.node.position, part.node.quaternion, part.node.scale)
    }
    root!.updateMatrixWorld(true)
  }

  function finalWorld(part: RestPart): THREE.Matrix4 {
    if (part.overrideEpoch === overrideEpoch) return part.overrideWorld
    if (part.finalEpoch === overrideEpoch) return part.finalWorld
    const parent = partsByNode.get(part.node.parent!)
    part.finalWorld.multiplyMatrices(parent ? finalWorld(parent) : part.node.parent!.matrixWorld, part.node.matrix)
    part.finalEpoch = overrideEpoch
    return part.finalWorld
  }

  function placeSpring(part: RestPart, lower: THREE.Vector3, upper: THREE.Vector3, clocking: number) {
    origin.addVectors(lower, upper).multiplyScalar(0.5)
    axis.subVectors(upper, lower).normalize()
    // spring_mount_geom.SpringPose.rotation_rows: local+X along loaded eyes,
    // local+Y along ±worldZ and local+Z perpendicular, preserving hook clocking.
    desired.makeBasis(axis, b.set(0, 0, clocking), c.set(clocking * axis.y, -clocking * axis.x, 0))
    desired.setPosition(origin)
    setWorld(part, desired)
  }

  function alignWire(part: RestPart, endpoints: ArrayLike<number>, from: number, to: number) {
    // Native straight cylinders are authored from local origin along local +Y.
    // Axial scaling does not scale the circular section or its source diameter.
    origin.set(endpoints[from]!, endpoints[from + 1]!, endpoints[from + 2]!)
    axis.set(endpoints[to]!, endpoints[to + 1]!, endpoints[to + 2]!).sub(origin)
    const length = axis.length()
    axis.divideScalar(length)
    const restDirection = b.setFromMatrixColumn(part.world, 1).normalize()
    quaternion.setFromUnitVectors(restDirection, axis)
    rotation.makeRotationFromQuaternion(quaternion)
    desired.copy(part.world)
    const restLength = part.wireLengthM!
    // Scale the native +Y basis only, then rigidly turn it into the solved run.
    desired.elements[4]! *= length / restLength
    desired.elements[5]! *= length / restLength
    desired.elements[6]! *= length / restLength
    desired.premultiply(rotation)
    desired.setPosition(origin)
    setWorld(part, desired)
  }

  function drivePaperPart(part: RestPart) {
    if (part === upperSprocket || part === crankSprocket || part === spareSprocket) return
    const name = part.shortName
    const knobAngle = pose.crankAngleRad * MECHANISM_DATA.paperDrive.chainRatioFine * PAPER_FEED_MULTIPLIER[input.gearing]
    const feedAngle = knobAngle * MECHANISM_DATA.paperDrive.externalMeshSense * MECHANISM_DATA.paperDrive.reducerRatio
    const angle = name === 'rack-pinion-1' || name === 'transgear-feed-pinion-1' ? feedAngle : knobAngle
    // Resetting a platen datum does not wind the feed gears; only crank turns do.
    pivot.setFromMatrixPosition(part.world)
    rotate(part, pivot, Z, angle)
  }

  function chainPoint(stationMm: number, out: THREE.Vector3) {
    const path = chain.paths[input.gearing]
    let distance = ((stationMm % chain.centrelineLengthMm) + chain.centrelineLengthMm) % chain.centrelineLengthMm
    for (const arc of path.arcsMm) {
      const arcLength = arc[2]! * arc[4]!
      if (distance <= arcLength) {
        const angle = arc[3]! + distance / arc[2]!
        const x = arc[0]! + arc[2]! * Math.cos(angle) + chain.knobCentrePreMirrorMm[0]
        const y = arc[1]! + arc[2]! * Math.sin(angle) + chain.knobCentrePreMirrorMm[1]
        out.set(-x / 1000, y / 1000, 0)
        return
      }
      distance -= arcLength
    }
    const line = path.tautMm
    const t = distance / path.tautLengthMm
    out.set(
      -(line[0] + t * (line[2] - line[0]) + chain.knobCentrePreMirrorMm[0]) / 1000,
      (line[1] + t * (line[3] - line[1]) + chain.knobCentrePreMirrorMm[1]) / 1000,
      0,
    )
  }

  function driveChainPart(part: RestPart) {
    if (part.chainStationMm === undefined) {
      warnOverride(part.path)
      return
    }
    // Native CONNECTED_LINKAGE placement resolves unequal arc stations to
    // fixed 6.35-mm chords. Preserve its actual rest TRS/offsets, rather than
    // replacing it with uniform arc spacing. Runtime motion follows the source
    // planar centreline display law; tooth contact and 3D chain flexibility are
    // not solved. The released closing seam has a measured 0.55228-mm gap.
    const advance = -chain.paths[input.gearing].crankPitchRadiusMm * pose.crankAngleRad
    chainPoint(part.chainStationMm + advance, origin)
    chainPoint(part.chainNextStationMm! + advance, b)
    const angle = Math.atan2(b.y - origin.y, b.x - origin.x)
    restAnchor.setFromMatrixPosition(part.world)
    origin.sub(part.chainRestCurveM!).add(restAnchor)
    endpoint(part, restAnchor, origin, angle - part.chainRestChordAngleRad!)
  }

  function sprocketAt(part: RestPart, frame: RestPart, angle: number) {
    desired.copy(frame.world)
    pivot.setFromMatrixPosition(desired)
    around(delta, pivot, Z, angle)
    desired.premultiply(delta)
    if (frame === crankSprocket) desired.premultiply(swing)
    setWorld(part, desired)
    part.node.visible = true
  }

  function driveSprockets() {
    if (!upperSprocket || !crankSprocket || !spareSprocket || !upperMedium || !crankMedium) return
    const knobAngle = pose.crankAngleRad * MECHANISM_DATA.paperDrive.chainRatioFine * PAPER_FEED_MULTIPLIER[input.gearing]
    if (input.gearing === 'medium-medium') {
      upperSprocket.node.visible = false
      crankSprocket.node.visible = false
      spareSprocket.node.visible = false
      sprocketAt(upperMedium, upperSprocket, knobAngle)
      sprocketAt(crankMedium, crankSprocket, pose.crankAngleRad)
    } else if (input.gearing === 'large-small') {
      sprocketAt(upperSprocket, crankSprocket, pose.crankAngleRad)
      sprocketAt(crankSprocket, upperSprocket, knobAngle)
    } else {
      sprocketAt(upperSprocket, upperSprocket, knobAngle)
      sprocketAt(crankSprocket, crankSprocket, pose.crankAngleRad)
    }
  }

  function springOwner(part: RestPart): RestPart | null {
    for (let node: THREE.Object3D | null = part.node; node && node !== root; node = node.parent) {
      const owner = partsByNode.get(node)
      if (owner?.spring) return owner
    }
    return null
  }

  function unsupportedDeformation(node: THREE.Object3D): string | null {
    let reason: string | null = null
    node.traverse(child => {
      if (reason || child.userData.landmarkMarker) return
      if (child instanceof THREE.SkinnedMesh) reason = 'native part uses GPU skinning, which the probe does not reproduce'
      else if (child instanceof THREE.InstancedMesh || child instanceof THREE.BatchedMesh) reason = 'native part uses GPU instancing/batching, which the probe does not reproduce'
      else if (child instanceof THREE.Mesh && Object.keys(child.geometry.morphAttributes).length > 0) reason = 'native part uses morph targets, which the probe does not reproduce'
    })
    return reason
  }

  function finitePoint(value: unknown): value is Point3 {
    return Array.isArray(value) && value.length === 3 && value.every(item => typeof item === 'number' && Number.isFinite(item))
  }

  function createLandmarkProbe(anchors: readonly LandmarkAnchor[]): LandmarkProbe {
    const pass = { value: 0 }
    const pointSize = { value: 1 }
    const rigidMaterial = markerMaterial(MARKER_VERTEX, { landmarkPass: pass, landmarkPointSize: pointSize })
    const materials: THREE.Material[] = [rigidMaterial]
    const springMaterials = new Map<SpringDeformer, THREE.ShaderMaterial>()
    const objects: THREE.Points[] = []
    const markers: ProbeMarker[] = []
    const seen = new Set<string>()
    const point = new THREE.Vector3()
    const relative = new THREE.Matrix4()
    const firstRelative = new THREE.Matrix4()
    const coordinates: SpringCoordinates = { kind: 0, t: 0, centre: new THREE.Vector3(), tangent: new THREE.Vector3() }
    let slots = 0
    root?.updateMatrixWorld(true)

    function marker(id: string, position: THREE.Vector3, material: THREE.ShaderMaterial, spring: SpringCoordinates | null): THREE.Points {
      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.Float32BufferAttribute([position.x, position.y, position.z], 3))
      geometry.setAttribute('landmarkSlot', new THREE.Float32BufferAttribute([slots], 1))
      if (spring) {
        // Exactly the per-vertex attributes the native swept-wire mesh carries.
        geometry.setAttribute('springCoordinate', new THREE.Float32BufferAttribute([spring.kind, spring.t], 2))
        geometry.setAttribute('springRestCentre', new THREE.Float32BufferAttribute(spring.centre.toArray(), 3))
        geometry.setAttribute('springRestTangent', new THREE.Float32BufferAttribute(spring.tangent.toArray(), 3))
      }
      const object = new THREE.Points(geometry, material)
      object.name = `landmark-probe:${id}`
      object.layers.set(PROBE_LAYER)
      object.frustumCulled = false
      object.userData.landmarkMarker = true
      objects.push(object)
      return object
    }

    function place(anchor: LandmarkAnchor, id: string): { object: THREE.Points } | { reason: string } {
      if (availability !== 'available' || !root) return { reason: `native model ${availability}; no native scene graph to measure` }
      const hasWorld = anchor.worldMetres !== undefined
      if (hasWorld === (anchor.partLocalMetres !== undefined)) return { reason: 'anchor needs exactly one of partLocalMetres or worldMetres' }
      if (anchor.partPath === undefined && hasWorld) {
        // Diagnostic only: no named part, so a stateless fixed CAD-world point.
        // Source observations always name their part and take the branch below.
        if (!finitePoint(anchor.worldMetres)) return { reason: 'worldMetres must be three finite metres' }
        const object = marker(id, point.fromArray(anchor.worldMetres), rigidMaterial, null)
        scene.add(object)
        return { object }
      }
      if (typeof anchor.partPath !== 'string') return { reason: 'partPath must name the anchor\'s native part' }
      const part = parts.get(anchor.partPath)
      if (!part) return { reason: `native part missing: ${anchor.partPath}` }
      if (hasWorld) {
        if (!finitePoint(anchor.worldMetres)) return { reason: 'worldMetres must be three finite metres' }
        if (part.world.determinant() === 0) return { reason: 'native part rest matrix is singular; worldMetres has no part-local coordinate' }
        // A fixed CAD-world point of the named part at its exported rest pose.
        // Its rest-local coordinate from the part's original matrix lands
        // exactly on worldMetres at rest, and follows the part's actual
        // visibility and any source override like its native geometry.
        point.fromArray(anchor.worldMetres).applyMatrix4(relative.copy(part.world).invert())
      } else {
        if (!finitePoint(anchor.partLocalMetres)) return { reason: 'partLocalMetres must be three finite metres' }
        point.fromArray(anchor.partLocalMetres)
      }
      const unsupported = unsupportedDeformation(part.node)
      if (unsupported) return { reason: unsupported }
      const owner = springOwner(part)
      if (!owner) {
        // Rigid or affine (wire) native node: the marker inherits its exact matrixWorld.
        const object = marker(id, point, rigidMaterial, null)
        part.node.add(object)
        return { object }
      }
      if (owner !== part) return { reason: 'anchor lies inside a deformed spring subtree; anchor the spring part itself' }
      const spring = owner.spring!
      const mesh = spring.meshes[0]
      if (!mesh) return { reason: 'spring has no deformed native mesh' }
      firstRelative.copy(mesh.matrixWorld).invert().multiply(owner.node.matrixWorld)
      for (const other of spring.meshes) {
        relative.copy(other.matrixWorld).invert().multiply(owner.node.matrixWorld)
        for (let i = 0; i < 16; i++) {
          if (Math.abs(relative.elements[i]! - firstRelative.elements[i]!) > 1e-9) return { reason: 'deformed spring meshes have differing geometry frames; deformation of this anchor is ambiguous' }
        }
      }
      // Into the mesh geometry frame, where the native vertex deformation acts.
      point.applyMatrix4(firstRelative)
      spring.markerCoordinates(point, coordinates)
      let material = springMaterials.get(spring)
      if (!material) {
        material = markerMaterial(MARKER_VERTEX, { landmarkPass: pass, landmarkPointSize: pointSize })
        spring.deform(material)
        springMaterials.set(spring, material)
        materials.push(material)
      }
      const object = marker(id, point, material, coordinates)
      mesh.add(object)
      return { object }
    }

    for (const anchor of anchors) {
      const id = typeof anchor?.id === 'string' ? anchor.id : ''
      let placed: { object: THREE.Points } | { reason: string }
      if (!id) placed = { reason: 'anchor id missing' }
      else if (seen.has(id)) placed = { reason: 'duplicate anchor id' }
      else placed = place(anchor, id)
      if (id) seen.add(id)
      if ('object' in placed) markers.push({ id, slot: slots++, reason: null, object: placed.object })
      else markers.push({ id, slot: -1, reason: placed.reason, object: null })
    }

    let status: LandmarkProbe['status'] = 'active'
    const probe: LandmarkProbe = {
      visibilityMode: 'depth-off-landmark-projection',
      anchors: markers.map(item => ({ id: item.id, state: item.slot >= 0 ? 'measurable' : 'unresolved', reason: item.reason })),
      get status() { return status },
      dispose() {
        if (status === 'disposed') return
        status = 'disposed'
        for (const object of objects) {
          object.removeFromParent()
          object.geometry.dispose()
        }
        for (const material of materials) material.dispose()
        objects.length = 0
        materials.length = 0
        markers.length = 0
        springMaterials.clear()
        probes.delete(probe)
        probeInternals.delete(probe)
      },
    }
    probes.add(probe)
    probeInternals.set(probe, { markers, passes: Math.ceil(slots / SLOTS_PER_PASS), pass, pointSize, revision })
    return probe
  }

  function synchronizeNativeInventory() {
    if (!root || availability !== 'available' || nativeInventoryRevision === inventoryRevision.value) return
    root.traverse(object => {
      if (object.userData.landmarkMarker || nativeDrawableSeen.has(object) || !(object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points)) return
      // Exported nodes retain their exact qualified CAD paths. Cloned native
      // instances inherit the instance owner's path plus their child names.
      const suffix: string[] = []
      let owner: RestPart | undefined
      for (let node: THREE.Object3D | null = object; node && node !== root; node = node.parent) {
        owner = partsByNode.get(node)
        if (owner) break
        suffix.push(typeof node.userData.name === 'string' ? node.userData.name : node.name)
      }
      let path = owner ? owner.path : ''
      for (let i = suffix.length - 1; i >= 0; i--) path += `/${suffix[i]}`
      if (!path || nativeDrawablePaths.includes(path)) throw new Error(`Native drawable lacks a unique qualified path: ${path}`)
      nativeDrawables.push({ path, object })
      nativeDrawablePaths.push(path)
      nativeDrawableSeen.add(object)
    })
    nativeInventoryRevision = inventoryRevision.value
  }

  function createPartVisibilityProbe(): PartVisibilityProbe {
    if (availability !== 'available' || !root) throw new Error('Native model is unavailable; a full-geometry visibility probe cannot be created.')
    const entries: NativeDrawable[] = []
    const drawablePaths: string[] = []
    const materials: THREE.Material[] = []
    let synchronizedRevision = -1
    let status: PartVisibilityProbe['status'] = 'active'

    function diagnostic(source: THREE.Material, id: number): THREE.Material {
      const result = source.clone()
      // Preserve the original shader (including the native swept-wire spring
      // hook, texture alpha, clipping, side and polygon-offset semantics).
      const nativeCompile = source.onBeforeCompile
      const nativeCacheKey = source.customProgramCacheKey()
      const colour = new THREE.Vector3((id & 255) / 255, ((id >>> 8) & 255) / 255, ((id >>> 16) & 255) / 255)
      result.onBeforeCompile = (shader, activeRenderer) => {
        nativeCompile.call(source, shader, activeRenderer)
        shader.uniforms.nativePathId = { value: colour }
        shader.fragmentShader = `uniform vec3 nativePathId;\n${shader.fragmentShader}`
        const end = shader.fragmentShader.lastIndexOf('}')
        shader.fragmentShader = `${shader.fragmentShader.slice(0, end)}\nif (diffuseColor.a <= 0.0) discard;\ngl_FragColor = vec4(nativePathId, 1.0);\n${shader.fragmentShader.slice(end)}`
      }
      result.customProgramCacheKey = () => `${nativeCacheKey}:native-path-id`
      result.blending = THREE.NoBlending
      result.depthTest = true
      result.depthWrite = true
      result.toneMapped = false
      materials.push(result)
      return result
    }

    function synchronize() {
      if (status !== 'active' || synchronizedRevision === inventoryRevision.value) return
      synchronizeNativeInventory()
      if (nativeDrawables.length > 0xffffff) throw new Error('Native visibility inventory exceeds RGB8 path IDs.')
      for (let i = entries.length; i < nativeDrawables.length; i++) {
        const drawable = nativeDrawables[i]!
        const original = drawable.object.material
        const id = i + 1
        const replacement = Array.isArray(original) ? original.map(material => diagnostic(material, id)) : diagnostic(original, id)
        entries.push({ path: drawable.path, object: drawable.object, original, diagnostic: replacement })
        drawablePaths.push(drawable.path)
      }
      synchronizedRevision = inventoryRevision.value
    }

    synchronize()
    const probe: PartVisibilityProbe = {
      visibilityMode: 'depth-tested-native-surfaces',
      get partPaths() { synchronize(); return drawablePaths },
      get status() { return status },
      dispose() {
        if (status === 'disposed') return
        status = 'disposed'
        for (const material of materials) material.dispose()
        materials.length = 0
        entries.length = 0
        drawablePaths.length = 0
        visibilityProbes.delete(probe)
        partVisibilityInternals.delete(probe)
      },
    }
    visibilityProbes.add(probe)
    partVisibilityInternals.set(probe, { entries, revision, inventoryRevision, synchronize })
    return probe
  }

  function addPartInstance(sourcePartPath: string, instancePath: string): 'added' | 'already-present' | 'missing-source' {
    if (parts.has(instancePath)) return 'already-present'
    const source = parts.get(sourcePartPath)
    if (!source || !root) { warnOverride(sourcePartPath); return 'missing-source' }
    const node = source.node.clone(true)
    // Diagnostic markers belong to their probe, never to a new native instance.
    const clonedMarkers: THREE.Object3D[] = []
    node.traverse(child => { if (child.userData.landmarkMarker) clonedMarkers.push(child) })
    for (const marker of clonedMarkers) marker.removeFromParent()
    source.node.parent!.add(node)
    node.userData.nativeInstanceSource = sourcePartPath
    node.userData.nativeInstancePath = instancePath
    const instance: RestPart = {
      ...source, path: instancePath, node, position: source.position.clone(), quaternion: source.quaternion.clone(),
      scale: source.scale.clone(), world: source.world.clone(), parentInverse: source.parentInverse.clone(), visible: false,
      overrideWorld: new THREE.Matrix4(), finalWorld: new THREE.Matrix4(), overrideEpoch: -1, finalEpoch: -1,
    }
    node.visible = false
    parts.set(instancePath, instance)
    partsByNode.set(node, instance)
    paths.push(instancePath)
    revision.value++
    inventoryRevision.value++
    return 'added'
  }

  function dispose() {
    for (const probe of [...probes]) probe.dispose()
    for (const probe of [...visibilityProbes]) probe.dispose()
    revision.value++
    if (root) {
      root.removeFromParent()
      disposeNativeObject(root)
    }
    root = null
    availability = 'unavailable'
    nativeDrawables.length = 0
    nativeDrawablePaths.length = 0
    parts.clear()
    paths.length = 0
    driven.length = 0
  }

  solveMechanism(input, pose)
  return {
    input, pose, missing, loadError, provenance, partPaths: paths, update, addPartInstance, createLandmarkProbe, createPartVisibilityProbe, dispose,
    get availability() { return availability },
    get nativeDrawablePartPaths() { synchronizeNativeInventory(); return nativeDrawablePaths },
  }
}

/** Free a detached native subtree's geometries, materials and textures. */
function disposeNativeObject(object: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>()
  const materials = new Set<THREE.Material>()
  const textures = new Set<THREE.Texture>()
  object.traverse(node => {
    if (!(node instanceof THREE.Mesh || node instanceof THREE.Line || node instanceof THREE.Points)) return
    geometries.add(node.geometry)
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) materials.add(material)
  })
  for (const material of materials) {
    for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value)
    material.dispose()
  }
  for (const geometry of geometries) geometry.dispose()
  for (const texture of textures) {
    texture.dispose()
    const image: unknown = texture.source.data
    if (typeof ImageBitmap !== 'undefined' && image instanceof ImageBitmap) image.close()
  }
}

function nativeWireLength(part: RestPart): number {
  let length = 0
  part.node.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return
    node.geometry.computeBoundingBox()
    const box = node.geometry.boundingBox!
    length = Math.max(length, box.max.y - box.min.y)
  })
  return length
}

interface SpringDeformer {
  length: { value: number }
  /** Meshes whose vertices this deformer's shader moves. */
  readonly meshes: readonly THREE.Mesh[]
  /** Install this spring's exact native vertex deformation on a material. */
  deform(material: THREE.Material): void
  /** The native per-vertex deformation attributes for a point in mesh geometry metres. */
  markerCoordinates(point: THREE.Vector3, out: SpringCoordinates): void
}
type SpringStock = 'channel' | 'counter'
interface SpringCoordinates {
  kind: number
  t: number
  centre: THREE.Vector3
  tangent: THREE.Vector3
}
const preparedSprings = new WeakMap<THREE.BufferGeometry, Map<string, THREE.BufferGeometry>>()

/**
 * Deform the authentic swept-wire mesh, not a replacement TubeGeometry.
 * Source: channel_spring_stock_geom.py / counter_spring_stock_geom.py and
 * diagnostics/diag_build_9432K31.py:109-159 at the pinned release commit.
 * Hook assemblies translate rigidly; coil centreline pitch changes with L.
 * A minimal tangent rotation preserves each original wire section's radius
 * (scaling vertex X itself would squash the wire). Buffers/programs allocate
 * only here. The frame loop changes one length uniform and one rigid matrix.
 */
function createSpringDeformer(node: THREE.Object3D, restLengthM: number, stock: SpringStock): SpringDeformer {
  const length = { value: restLengthM }
  const rest = { value: restLengthM }
  const counter = stock === 'counter'
  const source = counter ? MECHANISM_DATA.counter : MECHANISM_DATA.spring
  const radius = (source.coilOutsideDiameterMm - source.wireDiameterMm) / 2000
  const wireRadius = source.wireDiameterMm / 2000
  const turns = source.coilTurns
  const inset = counter ? 0.0102997 : source.insideDiameterMm / 1000
  const endCorrection = counter ? wireRadius : 0
  const point = new THREE.Vector3()
  const residue = new THREE.Vector3()
  const coordinates: SpringCoordinates = { kind: 0, t: 0, centre: new THREE.Vector3(), tangent: new THREE.Vector3() }
  const trial = new THREE.Vector3()
  const trialTangent = new THREE.Vector3()

  // The transition is the vendor's own clamped cubic, in metres. Only its
  // coil-end handle changes direction; the rigid hook and hook-end handle do not.
  function curve(kind: number, t: number, span: number, out: THREE.Vector3, direction: THREE.Vector3) {
    if (kind === 0) {
      const height = span - 2 * inset - endCorrection
      const angle = t * turns * 2 * Math.PI
      out.set(-span / 2 + inset + height * t, -radius * Math.sin(angle), radius * Math.cos(angle))
      direction.set(height, -radius * turns * 2 * Math.PI * Math.cos(angle), -radius * turns * 2 * Math.PI * Math.sin(angle)).normalize()
      return
    }
    const shift = -(span - 0.0494792) / 2
    const pitch = (span - 2 * inset) / turns
    const radial = Math.atan2(-radius, pitch / (2 * Math.PI))
    const polar = -0.00014851266501942706
    const bx = -0.0197104 + shift
    const x0 = -0.022225 + shift
    const x1 = -0.0206375 + shift
    const x2 = bx - 0.0015875 * Math.cos(radial) * Math.cos(polar)
    const y2 = -0.0015875 * Math.sin(radial) * Math.cos(polar)
    const z2 = radius - 0.0015875 * Math.sin(polar)
    const u = 1 - t
    out.set(
      u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * bx,
      u * u * u * radius + 3 * u * u * t * radius + 3 * u * t * t * y2,
      3 * u * t * t * z2 + t * t * t * radius,
    )
    direction.set(
      3 * u * u * (x1 - x0) + 6 * u * t * (x2 - x1) + 3 * t * t * (bx - x2),
      6 * u * t * (y2 - radius) - 3 * t * t * y2,
      6 * u * t * z2 + 3 * t * t * (radius - z2),
    ).normalize()
    if (kind > 0) { out.x = -out.x; out.z = -out.z; direction.x = -direction.x; direction.z = -direction.z }
  }

  function classify(vertex: THREE.Vector3, result: SpringCoordinates) {
    const start = -restLengthM / 2 + inset
    const height = restLengthM - 2 * inset - endCorrection
    // End loops, the counter's asymmetric half-turn and its source transitions
    // all form rigid end assemblies. Do not stretch those with the coil.
    result.kind = vertex.x < 0 ? -2 : 2
    result.t = 0
    result.centre.copy(vertex)
    result.tangent.set(1, 0, 0)
    let best = Infinity
    const initial = (vertex.x - start) / height
    const azimuth = Math.atan2(-vertex.y, vertex.z) / (2 * Math.PI)
    const winding = Math.round(initial * turns - azimuth)
    for (let neighbouringTurn = -1; neighbouringTurn <= 1; neighbouringTurn++) {
      let t = Math.min(1, Math.max(0, (winding + neighbouringTurn + azimuth) / turns))
      // Fixed-winding nearest point, including the wire's axial radial offset.
      for (let n = 0; n < 6; n++) {
        curve(0, t, restLengthM, trial, trialTangent)
        residue.subVectors(vertex, trial)
        const speed = Math.hypot(height, radius * turns * 2 * Math.PI)
        t = Math.min(1, Math.max(0, t + residue.dot(trialTangent) / speed))
      }
      curve(0, t, restLengthM, trial, trialTangent)
      const distance = vertex.distanceToSquared(trial)
      if (distance < best) {
        best = distance
        result.kind = 0; result.t = t
        result.centre.copy(trial); result.tangent.copy(trialTangent)
      }
    }
    if (!counter && Math.abs(vertex.x) > restLengthM / 2 - inset - wireRadius) {
      // Keep the half-circle hook rigid; compare its source centreline with
      // the transition before selecting the elastic transition parameter.
      const side = vertex.x < 0 ? -1 : 1
      const eyeX = side * (restLengthM - source.insideDiameterMm / 1000) / 2
      const hookRadius = Math.hypot(vertex.x - eyeX, vertex.y)
      const hookDistance = (hookRadius - radius) ** 2 + vertex.z * vertex.z
      if (side * (vertex.x - eyeX) >= 0 && hookDistance < best) {
        best = hookDistance
        result.kind = side * 2
        result.centre.copy(vertex); result.tangent.set(1, 0, 0)
      }
      const kind = side
      let chosenT = 0
      let curveDistance = Infinity
      for (let sample = 0; sample <= 32; sample++) {
        const t = sample / 32
        curve(kind, t, restLengthM, trial, trialTangent)
        const distance = vertex.distanceToSquared(trial)
        if (distance < curveDistance) { curveDistance = distance; chosenT = t }
      }
      // Local one-dimensional golden minimization, entirely initialization.
      let lo = Math.max(0, chosenT - 1 / 32)
      let hi = Math.min(1, chosenT + 1 / 32)
      for (let n = 0; n < 18; n++) {
        const left = lo + (hi - lo) * 0.3819660112501051
        const right = hi - (hi - lo) * 0.3819660112501051
        curve(kind, left, restLengthM, trial, trialTangent)
        const dl = vertex.distanceToSquared(trial)
        curve(kind, right, restLengthM, trial, trialTangent)
        if (dl < vertex.distanceToSquared(trial)) hi = right; else lo = left
      }
      const t = (lo + hi) / 2
      curve(kind, t, restLengthM, trial, trialTangent)
      if (vertex.distanceToSquared(trial) < best) {
        result.kind = kind; result.t = t
        result.centre.copy(trial); result.tangent.copy(trialTangent)
      }
    }
    // The counter's loop/transition sweeps overlap the coil end planes. Their
    // own sections are rigid: classify non-coil surfaces by centreline distance.
    if (counter && (vertex.x < start || vertex.x > start + height || best > wireRadius * wireRadius * 1.08)) {
      result.kind = vertex.x < 0 ? -2 : 2
      result.centre.copy(vertex); result.tangent.set(1, 0, 0)
    }
  }

  const shaderFunctions = `
attribute vec2 springCoordinate;
attribute vec3 springRestCentre;
attribute vec3 springRestTangent;
uniform float springLength;
uniform float springRestLength;
vec3 springTurn(vec3 v, vec3 from, vec3 to) {
  vec3 crossAxis = cross(from, to);
  float cosine = dot(from, to);
  return v + cross(crossAxis, v) + cross(crossAxis, cross(crossAxis, v)) / max(1.0 + cosine, 0.000001);
}
void springCurve(out vec3 centre, out vec3 tangent) {
  float kind = springCoordinate.x;
  float t = springCoordinate.y;
  if (abs(kind) > 1.5) {
    centre = springRestCentre + vec3(sign(kind) * (springLength - springRestLength) * 0.5, 0.0, 0.0);
    tangent = springRestTangent;
  } else if (abs(kind) < 0.5) {
    float height = springLength - ${2 * inset + endCorrection};
    float angle = t * ${turns * 2 * Math.PI};
    centre = vec3(-springLength * 0.5 + ${inset} + height * t, -${radius} * sin(angle), ${radius} * cos(angle));
    tangent = normalize(vec3(height, -${radius * turns * 2 * Math.PI} * cos(angle), -${radius * turns * 2 * Math.PI} * sin(angle)));
  } else {
    float shift = -(springLength - 0.0494792) * 0.5;
    float pitch = (springLength - ${2 * inset}) / ${turns.toFixed(1)};
    float radial = atan(-${radius}, pitch / 6.283185307179586);
    vec3 p0 = vec3(-0.022225 + shift, ${radius}, 0.0);
    vec3 p1 = vec3(-0.0206375 + shift, ${radius}, 0.0);
    vec3 p3 = vec3(-0.0197104 + shift, 0.0, ${radius});
    vec3 p2 = p3 - 0.0015875 * vec3(cos(radial) * cos(-0.00014851266501942706), sin(radial) * cos(-0.00014851266501942706), sin(-0.00014851266501942706));
    float u = 1.0 - t;
    centre = u*u*u*p0 + 3.0*u*u*t*p1 + 3.0*u*t*t*p2 + t*t*t*p3;
    tangent = normalize(3.0*u*u*(p1-p0) + 6.0*u*t*(p2-p1) + 3.0*t*t*(p3-p2));
    if (kind > 0.0) { centre.xz *= -1.0; tangent.xz *= -1.0; }
  }
}
`
  // The single deformation hook: native spring meshes and probe markers both
  // compile exactly this vertex code against the same length uniforms.
  function deform(material: THREE.Material) {
    material.onBeforeCompile = shader => {
      shader.uniforms.springLength = length
      shader.uniforms.springRestLength = rest
      shader.vertexShader = shaderFunctions + shader.vertexShader
      shader.vertexShader = shader.vertexShader.replace('#include <beginnormal_vertex>', `
#include <beginnormal_vertex>
vec3 springNewCentre;
vec3 springNewTangent;
springCurve(springNewCentre, springNewTangent);
objectNormal = springTurn(objectNormal, springRestTangent, springNewTangent);
`)
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', `
vec3 transformed = springNewCentre + springTurn(position - springRestCentre, springRestTangent, springNewTangent);
`)
    }
    material.customProgramCacheKey = () => `native-stock-spring:${stock}`
  }
  const deformedClone = (sourceMaterial: THREE.Material) => {
    const result = sourceMaterial.clone()
    deform(result)
    return result
  }
  const meshes: THREE.Mesh[] = []
  node.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    const original = object.geometry
    let versions = preparedSprings.get(original)
    if (!versions) { versions = new Map(); preparedSprings.set(original, versions) }
    const cacheKey = `${stock}:${restLengthM}`
    let geometry = versions.get(cacheKey)
    if (!geometry) {
      const prepared = original.clone()
      const position = original.getAttribute('position')
      const parameters = new Float32Array(position.count * 2)
      const centres = new Float32Array(position.count * 3)
      const tangents = new Float32Array(position.count * 3)
      for (let i = 0; i < position.count; i++) {
        point.fromBufferAttribute(position, i)
        classify(point, coordinates)
        parameters[i * 2] = coordinates.kind; parameters[i * 2 + 1] = coordinates.t
        coordinates.centre.toArray(centres, i * 3)
        coordinates.tangent.toArray(tangents, i * 3)
      }
      prepared.setAttribute('springCoordinate', new THREE.BufferAttribute(parameters, 2))
      prepared.setAttribute('springRestCentre', new THREE.BufferAttribute(centres, 3))
      prepared.setAttribute('springRestTangent', new THREE.BufferAttribute(tangents, 3))
      versions.set(cacheKey, prepared)
      geometry = prepared
    }
    object.geometry = geometry
    // Source bounding spheres describe the saved length, not the extended coil.
    object.frustumCulled = false
    meshes.push(object)
    object.material = Array.isArray(object.material) ? object.material.map(deformedClone) : deformedClone(object.material)
  })
  return {
    length,
    meshes,
    deform,
    markerCoordinates(vertex, out) {
      // Eye/bore anchors are in a rigid end assembly even though their bore
      // centres do not lie on the swept-wire surface used for classification;
      // kind ±2 makes the native shader translate them with that assembly.
      const restEyeX = (restLengthM - source.insideDiameterMm / 1000) / 2
      if (Math.abs(vertex.x) >= restEyeX) {
        out.kind = vertex.x < 0 ? -2 : 2
        out.t = 0
        out.centre.copy(vertex)
        out.tangent.set(1, 0, 0)
        return
      }
      classify(vertex, out)
    },
  }
}
