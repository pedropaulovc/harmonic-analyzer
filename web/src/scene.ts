import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
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
export interface SourceView {
  /** Stable view identity; GPU landmark captures are keyed by it. */
  id: string
  camera: CameraRecord
  /** Top-left source pixels, then width and height; source is 1920 × 1080. */
  rectSourcePixels: readonly [number, number, number, number]
  presentation?: Presentation
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
  readonly anchors: readonly LandmarkProbeAnchor[]
  readonly status: 'active' | 'disposed'
  dispose(): void
}
export type RenderedLandmarkState = 'rendered' | 'unresolved' | 'not-visible'
export interface RenderedLandmark {
  id: string
  state: RenderedLandmarkState
  /** CSS pixels from the canvas top-left, y down; continuous (pixel centres at +0.5). */
  canvasPixels: [number, number] | null
  /** 1920 × 1080 source-frame pixels, top-left origin, y down; continuous. */
  sourcePixels: [number, number] | null
  /** Per-axis raster/resampling quantization bound of canvasPixels, CSS pixels. */
  uncertaintyCanvasPixels: number | null
  reason: string | null
}
export interface RenderedLandmarks {
  method: 'gpu-readback'
  viewId: string
  presentation: Presentation
  /** Source time given to the capturing renderViews; null for exploring render(). */
  timeSeconds: number | null
  landmarks: RenderedLandmark[]
}
export interface PartOverride {
  partPath: string
  visibility?: 'visible' | 'hidden'
  worldPositionMetres?: Point3
  worldQuaternion?: Quaternion4
}
export interface ModelProvenance {
  sourceCommit: string
  expectedSha256: string
  observedSha256: string | null
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
  update(input: MechanismInput, overrides?: readonly PartOverride[]): void
  /** Add another genuine native part instance, sharing its original geometry. */
  addPartInstance(sourcePartPath: string, instancePath: string): 'added' | 'already-present' | 'missing-source'
  /** Diagnostic GPU markers on actual native nodes; install with Viewer.setLandmarkProbe. */
  createLandmarkProbe(anchors: readonly LandmarkAnchor[]): LandmarkProbe
  /** Remove the native root from the scene and free its GPU resources and probes. */
  dispose(): void
}
export interface LoadMachineOptions {
  /** GLB location; defaults to the pinned harmonic-analyzer export. */
  url?: string
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
  renderViews(views: readonly SourceView[], beforeView: ((view: SourceView, index: number) => void) | undefined, timeSeconds: number): void
  applyCamera(record: CameraRecord): void
  setInteraction(mode: InteractionMode): void
  fitView(object?: THREE.Object3D): void
  /** Install a probe (disposing any previous one), or null to restore plain native rendering. */
  setLandmarkProbe(probe: LandmarkProbe | null): void
  /** Read the capture made by the most recent draw of viewId; never rerenders. */
  readRenderedLandmarks(viewId: string): RenderedLandmarks | null
}

export const EXPLORING_VIEW_ID = 'exploring'
const SOURCE_WIDTH = 1920
const SOURCE_HEIGHT = 1080
const FULL_FRAME: readonly [number, number, number, number] = [0, 0, SOURCE_WIDTH, SOURCE_HEIGHT]
const MODEL_URL = `${import.meta.env.BASE_URL}models/harmonic-analyzer.glb`
const Z = new THREE.Vector3(0, 0, 1)
const Y = new THREE.Vector3(0, 1, 0)

/** Diagnostic markers live only on this layer; native cameras never enable it. */
const PROBE_LAYER = 31
/** One bit per marker across RGBA8; additive blending keeps overlapping markers separable. */
const SLOTS_PER_PASS = 32
/** Reference markers at these NDC corners measure each view's actual viewport placement. */
const REFERENCE_NDC = 0.75
const REFERENCE_SOURCE_LOW = (1 - REFERENCE_NDC) / 2
const REFERENCE_SOURCE_SPAN = REFERENCE_NDC
const ACCUMULATOR_STRIDE = 7

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
  reasons: (string | null)[]
}
const CAPTURE_STATES: readonly RenderedLandmarkState[] = ['rendered', 'unresolved', 'not-visible']
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
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x11131a)
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
  mirrorScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mirrorMaterial))

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
  const probeViewport = new THREE.Vector4()
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
    writeCamera(camera, record, SOURCE_WIDTH, SOURCE_HEIGHT)
    if (mode === 'exploring') rebaseControls()
  }

  function setInteraction(next: InteractionMode) {
    if (next === mode) return
    mode = next
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
    renderer.setScissor(left, bottom, w, h)
  }

  /**
   * One view's draw into `output` (null = canvas). The landmark probe calls
   * this same function, so its markers take the identical viewport/scissor
   * calls, mirror stage and blit as the native image.
   */
  function drawView(rect: readonly [number, number, number, number], presentation: Presentation, output: THREE.WebGLRenderTarget | null, mirrorStage: THREE.WebGLRenderTarget, clearOutput: boolean) {
    if (presentation === 'horizontal-mirror') {
      // The mirror stage uses its own full viewport with scissor disabled;
      // renderer.setViewport would wrongly scale it by the canvas pixel ratio.
      renderer.setRenderTarget(mirrorStage)
      renderer.clear(true, true, true)
      renderer.render(scene, camera)
      renderer.setRenderTarget(output)
      renderer.setScissorTest(true)
      viewport(rect[0], rect[1], rect[2], rect[3])
      if (clearOutput) renderer.clear(true, false, false)
      mirrorMaterial.uniforms.image!.value = mirrorStage.texture
      renderer.render(mirrorScene, mirrorCamera)
    } else {
      renderer.setRenderTarget(output)
      renderer.setScissorTest(true)
      viewport(rect[0], rect[1], rect[2], rect[3])
      if (clearOutput) renderer.clear(true, false, false)
      renderer.render(scene, camera)
    }
  }

  function render() {
    if (mode === 'exploring') controls.update()
    drawEpoch++
    beginFrame()
    camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
    camera.updateProjectionMatrix()
    drawView(FULL_FRAME, 'native', null, mirrorTarget, false)
    captureView(EXPLORING_VIEW_ID, FULL_FRAME, 'native', null)
    renderer.setScissorTest(false)
  }

  function renderViews(views: readonly SourceView[], beforeView: ((view: SourceView, index: number) => void) | undefined, timeSeconds: number) {
    drawEpoch++
    beginFrame()
    for (let i = 0; i < views.length; i++) {
      const view = views[i]!
      const rect = view.rectSourcePixels
      const presentation = view.presentation ?? 'native'
      beforeView?.(view, i)
      writeCamera(camera, view.camera, rect[2], rect[3])
      drawView(rect, presentation, null, mirrorTarget, false)
      // Same pose, camera and GL state as the draw just issued.
      captureView(view.id, rect, presentation, timeSeconds)
    }
    renderer.setScissorTest(false)
  }

  function ensureProbeTargets(): [THREE.WebGLRenderTarget, THREE.WebGLRenderTarget] {
    // Actual drawing-buffer size, not the renderer's cached logical size.
    const width = gl.drawingBufferWidth
    const height = gl.drawingBufferHeight
    const options = { depthBuffer: false, stencilBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, generateMipmaps: false, type: THREE.UnsignedByteType }
    if (!probeTarget) probeTarget = new THREE.WebGLRenderTarget(width, height, options)
    else if (probeTarget.width !== width || probeTarget.height !== height) probeTarget.setSize(width, height)
    if (!probeMirrorTarget) probeMirrorTarget = new THREE.WebGLRenderTarget(mirrorTarget.width, mirrorTarget.height, options)
    else if (probeMirrorTarget.width !== mirrorTarget.width || probeMirrorTarget.height !== mirrorTarget.height) probeMirrorTarget.setSize(mirrorTarget.width, mirrorTarget.height)
    return [probeTarget, probeMirrorTarget]
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

  function captureView(viewId: string, rect: readonly [number, number, number, number], presentation: Presentation, timeSeconds: number | null) {
    const internals = probe?.status === 'active' ? probeInternals.get(probe) : undefined
    if (!internals) return
    const markers = internals.markers
    let capture = captures.get(viewId)
    if (!capture) {
      capture = { epoch: -1, presentation, timeSeconds, states: new Uint8Array(markers.length), values: new Float64Array(markers.length * 5), reasons: new Array<string | null>(markers.length).fill(null) }
      captures.set(viewId, capture)
    }
    capture.epoch = drawEpoch
    capture.presentation = presentation
    capture.timeSeconds = timeSeconds
    for (let i = 0; i < markers.length; i++) {
      capture.states[i] = 1
      capture.reasons[i] = markers[i]!.slot < 0 ? markers[i]!.reason : 'GPU capture did not reach this marker'
    }
    if (internals.passes === 0) return
    const [target, mirrorStage] = ensureProbeTargets()
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
      const x0 = Math.max(0, probeViewport.x)
      const y0 = Math.max(0, probeViewport.y)
      const x1 = Math.min(target.width, probeViewport.x + probeViewport.z)
      const y1 = Math.min(target.height, probeViewport.y + probeViewport.w)
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
      if (bx === ax || by === ay) {
        markAll(capture, markers, 'view reference markers coincide; viewport mapping degenerate')
        return
      }
      const cssX = canvas.clientWidth / gl.drawingBufferWidth
      const cssY = canvas.clientHeight / gl.drawingBufferHeight
      const mirror = presentation === 'horizontal-mirror'
      const ratioX = mirror ? mirrorStage.width / probeViewport.z : 1
      const ratioY = mirror ? mirrorStage.height / probeViewport.w : 1
      // Nearest-sampled through the real blit, a marker must span at least one
      // destination sample; an odd square keeps its centre on the anchor.
      const pointSize = mirror ? 2 * Math.ceil(Math.max(ratioX, ratioY, 1) / 2) + 1 : 1
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
          let uncertaintyX = 0.5
          let uncertaintyY = 0.5
          if (mirror) {
            uncertaintyX += 0.5 / ratioX
            uncertaintyY += 0.5 / ratioY
            // A marker cut by the view edge loses part of its square.
            if (accumulators[o + 3]! - 0.5 <= x0 || accumulators[o + 4]! + 0.5 >= x1) uncertaintyX += pointSize / (2 * ratioX)
            if (accumulators[o + 5]! - 0.5 <= y0 || accumulators[o + 6]! + 0.5 >= y1) uncertaintyY += pointSize / (2 * ratioY)
          }
          const v = i * 5
          capture.states[i] = 0
          capture.reasons[i] = null
          capture.values[v] = px * cssX
          capture.values[v + 1] = (gl.drawingBufferHeight - py) * cssY
          capture.values[v + 2] = rect[0] + rect[2] * (REFERENCE_SOURCE_LOW + REFERENCE_SOURCE_SPAN * (px - ax) / (bx - ax))
          capture.values[v + 3] = rect[1] + rect[3] * (REFERENCE_SOURCE_LOW + REFERENCE_SOURCE_SPAN * (py - ay) / (by - ay))
          capture.values[v + 4] = Math.max(uncertaintyX * cssX, uncertaintyY * cssY)
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
    referenceGeometry.dispose()
    referenceMaterial.dispose()
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
    if (!internals || !capture || capture.epoch !== drawEpoch) return null
    return {
      method: 'gpu-readback', viewId, presentation: capture.presentation, timeSeconds: capture.timeSeconds,
      landmarks: internals.markers.map((marker, i) => {
        const rendered = capture.states[i] === 0
        const v = i * 5
        return {
          id: marker.id,
          state: CAPTURE_STATES[capture.states[i]!]!,
          canvasPixels: rendered ? [capture.values[v]!, capture.values[v + 1]!] : null,
          sourcePixels: rendered ? [capture.values[v + 2]!, capture.values[v + 3]!] : null,
          uncertaintyCanvasPixels: rendered ? capture.values[v + 4]! : null,
          reason: capture.reasons[i]!,
        }
      }),
    }
  }

  resize()
  return {
    renderer, scene, camera, resize, render, renderViews, applyCamera, setInteraction, fitView, setLandmarkProbe, readRenderedLandmarks,
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
  const probes = new Set<LandmarkProbe>()
  const provenance: ModelProvenance = {
    sourceCommit: MECHANISM_DATA.provenance.sourceCommit,
    expectedSha256: MECHANISM_DATA.provenance.modelSha256,
    observedSha256: null, generator: null, identity: 'unavailable', url,
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
    provenance.identity = provenance.observedSha256 === provenance.expectedSha256 ? 'matched' : 'mismatched'
    if (provenance.identity === 'mismatched') {
      availability = 'incompatible'
      missing.push(`Model identity mismatch: ${provenance.observedSha256}; model not parsed or added to the scene`)
    } else {
      const gltf = await new GLTFLoader().parseAsync(buffer, new URL('.', new URL(url, location.href)).href)
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
        probes.delete(probe)
        probeInternals.delete(probe)
      },
    }
    probes.add(probe)
    probeInternals.set(probe, { markers, passes: Math.ceil(slots / SLOTS_PER_PASS), pass, pointSize })
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
    const instance: RestPart = {
      ...source, path: instancePath, node, position: source.position.clone(), quaternion: source.quaternion.clone(),
      scale: source.scale.clone(), world: source.world.clone(), parentInverse: source.parentInverse.clone(), visible: false,
      overrideWorld: new THREE.Matrix4(), finalWorld: new THREE.Matrix4(), overrideEpoch: -1, finalEpoch: -1,
    }
    node.visible = false
    parts.set(instancePath, instance)
    partsByNode.set(node, instance)
    paths.push(instancePath)
    return 'added'
  }

  function dispose() {
    for (const probe of [...probes]) probe.dispose()
    if (root) {
      root.removeFromParent()
      disposeNativeObject(root)
    }
    root = null
    availability = 'unavailable'
    parts.clear()
    paths.length = 0
    driven.length = 0
  }

  solveMechanism(input, pose)
  return {
    input, pose, missing, loadError, provenance, partPaths: paths, update, addPartInstance, createLandmarkProbe, dispose,
    get availability() { return availability },
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
