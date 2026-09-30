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
export interface SourceView {
  camera: CameraRecord
  /** Top-left source pixels, then width and height; source is 1920 × 1080. */
  rectSourcePixels: readonly [number, number, number, number]
  presentation?: 'native' | 'horizontal-mirror'
}
export interface Projection {
  sourcePixels: [number, number]
  viewportPixels: [number, number]
  visibility: 'visible' | 'outside-viewport' | 'behind-camera'
  /** Positive camera-forward distance in metres. */
  depth: number
}
export type Anchor = { partPath: string; partLocalMetres: Point3 } | { worldMetres: Point3 }
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
  anchorWorld(anchor: Anchor, target?: Float64Array): Float64Array | null
  projectAnchor(anchor: Anchor, viewer: Pick<Viewer, 'projectWorld'>, target?: Projection, view?: SourceView): Projection | null
  /** Add another genuine native part instance, sharing its original geometry. */
  addPartInstance(sourcePartPath: string, instancePath: string): 'added' | 'already-present' | 'missing-source'
}

export interface Viewer {
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  controls: OrbitControls
  resize(): void
  render(): void
  renderViews(views: readonly SourceView[], beforeView?: (view: SourceView, index: number) => void): void
  applyCamera(record: CameraRecord): void
  setInteraction(mode: InteractionMode): void
  fitView(object?: THREE.Object3D): void
  projectWorld(world: ArrayLike<number>, target?: Projection, view?: SourceView): Projection
}

const SOURCE_WIDTH = 1920
const SOURCE_HEIGHT = 1080
const MODEL_URL = `${import.meta.env.BASE_URL}models/harmonic-analyzer.glb`
const Z = new THREE.Vector3(0, 0, 1)
const Y = new THREE.Vector3(0, 1, 0)

export function createProjection(): Projection {
  return { sourcePixels: [0, 0], viewportPixels: [0, 0], visibility: 'outside-viewport', depth: 0 }
}

/** Source cameras and every mechanical point remain in the original metre CAD frame. */
export function createViewer(canvas: HTMLCanvasElement): Viewer {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.autoClear = false
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x11131a)
  const camera = new THREE.PerspectiveCamera(35, SOURCE_WIDTH / SOURCE_HEIGHT, 0.005, 100)
  camera.setViewOffset(SOURCE_WIDTH, SOURCE_HEIGHT, 0, 0, SOURCE_WIDTH, SOURCE_HEIGHT)
  camera.clearViewOffset()
  camera.position.set(1.2, 1, 1.6)
  const controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 0.68, 0)
  controls.enableDamping = false
  let mode: InteractionMode = 'exploring'
  scene.add(new THREE.HemisphereLight(0xffffff, 0x404050, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(2, 3, 2)
  scene.add(key)

  const gate = { x: 0, y: 0, width: 1, height: 1 }
  const point = new THREE.Vector3()
  const forward = new THREE.Vector3()
  const projectionCamera = new THREE.PerspectiveCamera(35, SOURCE_WIDTH / SOURCE_HEIGHT, 0.005, 100)
  projectionCamera.setViewOffset(SOURCE_WIDTH, SOURCE_HEIGHT, 0, 0, SOURCE_WIDTH, SOURCE_HEIGHT)
  projectionCamera.clearViewOffset()
  const bounds = new THREE.Box3()
  const centre = new THREE.Vector3()
  const size = new THREE.Vector3()
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

  function applyCamera(record: CameraRecord) {
    writeCamera(camera, record, SOURCE_WIDTH, SOURCE_HEIGHT)
  }

  function setInteraction(next: InteractionMode) {
    if (next === mode) return
    mode = next
    controls.enabled = next === 'exploring'
    if (next === 'exploring') {
      // Rebuild OrbitControls from this exact source pose, including roll. No
      // stale spherical delta from a previous exploration may hit a source shot.
      const distance = Math.max(camera.position.distanceTo(controls.target), 0.1)
      forward.set(0, 0, -1).applyQuaternion(camera.quaternion)
      controls.target.copy(camera.position).addScaledVector(forward, distance)
      camera.up.set(0, 1, 0).applyQuaternion(camera.quaternion)
      controls.update()
    }
  }

  function fitView(object: THREE.Object3D = scene) {
    bounds.setFromObject(object)
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
    if (mode === 'exploring') controls.update()
  }

  function beginFrame() {
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

  function render() {
    if (mode === 'exploring') controls.update()
    beginFrame()
    camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
    camera.updateProjectionMatrix()
    viewport(0, 0, SOURCE_WIDTH, SOURCE_HEIGHT)
    renderer.render(scene, camera)
    renderer.setScissorTest(false)
  }

  function renderViews(views: readonly SourceView[], beforeView?: (view: SourceView, index: number) => void) {
    beginFrame()
    for (let i = 0; i < views.length; i++) {
      const view = views[i]!
      const rect = view.rectSourcePixels
      beforeView?.(view, i)
      writeCamera(camera, view.camera, rect[2], rect[3])
      if (view.presentation === 'horizontal-mirror') {
        renderer.setRenderTarget(mirrorTarget)
        renderer.setScissorTest(false)
        renderer.setViewport(0, 0, mirrorTarget.width, mirrorTarget.height)
        renderer.clear(true, true, true)
        renderer.render(scene, camera)
        renderer.setRenderTarget(null)
        renderer.setScissorTest(true)
        viewport(rect[0], rect[1], rect[2], rect[3])
        renderer.render(mirrorScene, mirrorCamera)
      } else {
        viewport(rect[0], rect[1], rect[2], rect[3])
        renderer.render(scene, camera)
      }
    }
    renderer.setScissorTest(false)
  }

  function projectWorld(world: ArrayLike<number>, target = createProjection(), view?: SourceView): Projection {
    let selectedCamera = camera
    let rx = 0, ry = 0, rw = SOURCE_WIDTH, rh = SOURCE_HEIGHT
    if (view) {
      const rect = view.rectSourcePixels
      rx = rect[0]; ry = rect[1]; rw = rect[2]; rh = rect[3]
      writeCamera(projectionCamera, view.camera, rw, rh)
      selectedCamera = projectionCamera
    } else {
      selectedCamera.updateMatrixWorld(true)
    }
    point.set(world[0]!, world[1]!, world[2]!).applyMatrix4(selectedCamera.matrixWorldInverse)
    target.depth = -point.z
    point.applyMatrix4(selectedCamera.projectionMatrix)
    const localX = (point.x + 1) * rw / 2
    const sx = rx + (view?.presentation === 'horizontal-mirror' ? rw - 1 - localX : localX)
    const sy = ry + (1 - point.y) * rh / 2
    target.sourcePixels[0] = sx
    target.sourcePixels[1] = sy
    target.viewportPixels[0] = gate.x + sx / SOURCE_WIDTH * gate.width
    target.viewportPixels[1] = gate.y + sy / SOURCE_HEIGHT * gate.height
    target.visibility = target.depth <= 0 ? 'behind-camera'
      : point.x < -1 || point.x > 1 || point.y < -1 || point.y > 1 || point.z < -1 || point.z > 1
        ? 'outside-viewport' : 'visible'
    return target
  }

  resize()
  return { renderer, scene, camera, controls, resize, render, renderViews, applyCamera, setInteraction, fitView, projectWorld }
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

/** Missing files/names warn and remain inspectable; they never count as verified fidelity. */
export async function loadMachine(scene: THREE.Scene): Promise<Machine> {
  const input = createMechanismInput()
  const pose = createMechanismPose()
  const missing: string[] = []
  const paths: string[] = []
  const parts = new Map<string, RestPart>()
  const partsByNode = new WeakMap<THREE.Object3D, RestPart>()
  let overrideEpoch = 0
  const driven: RestPart[] = []
  const overridesSeen = new Set<string>()
  const provenance: ModelProvenance = {
    sourceCommit: MECHANISM_DATA.provenance.sourceCommit,
    expectedSha256: MECHANISM_DATA.provenance.modelSha256,
    observedSha256: null, generator: null, identity: 'unavailable', url: MODEL_URL,
  }
  let availability: Machine['availability'] = 'unavailable'
  let loadError: string | null = null
  let root: THREE.Object3D | null = null
  try {
    const response = await fetch(MODEL_URL)
    if (!response.ok) throw new Error(`Model request returned HTTP ${response.status}`)
    const buffer = await response.arrayBuffer()
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))
    provenance.observedSha256 = Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('')
    const gltf = await new GLTFLoader().parseAsync(buffer, new URL('.', new URL(MODEL_URL, location.href)).href)
    provenance.generator = gltf.asset.generator ?? null
    provenance.identity = provenance.observedSha256 === provenance.expectedSha256 ? 'matched' : 'mismatched'
    availability = provenance.identity === 'matched' ? 'available' : 'incompatible'
    root = gltf.scene
    scene.add(root)
    root.updateMatrixWorld(true)
    function visit(node: THREE.Object3D, parentPath: string) {
      const originalName = typeof node.userData.name === 'string' ? node.userData.name : node.name
      const path = parentPath ? `${parentPath}/${originalName}` : originalName
      if (node !== root) {
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
      for (const child of node.children) visit(child, node === root ? '' : path)
    }
    visit(root, '')
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
    if (availability === 'incompatible') missing.push(`Model identity mismatch: ${provenance.observedSha256}; source pivots are not applied`)
  } catch (error) {
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
  const outputAnchor = new Float64Array(3)
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

  function anchorWorld(anchor: Anchor, target = outputAnchor): Float64Array | null {
    if ('worldMetres' in anchor) {
      target[0] = anchor.worldMetres[0]; target[1] = anchor.worldMetres[1]; target[2] = anchor.worldMetres[2]
      return target
    }
    const part = parts.get(anchor.partPath)
    if (!part) return null
    part.node.updateWorldMatrix(true, false)
    origin.fromArray(anchor.partLocalMetres)
    if (part.spring) part.spring.mapPoint(origin)
    origin.applyMatrix4(part.node.matrixWorld)
    target[0] = origin.x; target[1] = origin.y; target[2] = origin.z
    return target
  }
  function projectAnchor(anchor: Anchor, viewer: Pick<Viewer, 'projectWorld'>, target?: Projection, view?: SourceView) {
    if ('partPath' in anchor) {
      const part = parts.get(anchor.partPath)
      if (!part) return null
      let node: THREE.Object3D | null = part.node
      while (node) { if (!node.visible) return null; node = node.parent }
    }
    const world = anchorWorld(anchor)
    return world ? viewer.projectWorld(world, target, view) : null
  }
  function addPartInstance(sourcePartPath: string, instancePath: string): 'added' | 'already-present' | 'missing-source' {
    if (parts.has(instancePath)) return 'already-present'
    const source = parts.get(sourcePartPath)
    if (!source || !root) { warnOverride(sourcePartPath); return 'missing-source' }
    const node = source.node.clone(true)
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
  solveMechanism(input, pose)
  return { input, pose, missing, availability, loadError, provenance, partPaths: paths, update, anchorWorld, projectAnchor, addPartInstance }
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
  mapPoint(point: THREE.Vector3): void
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
  const centre = new THREE.Vector3()
  const tangent = new THREE.Vector3()
  const oldTangent = new THREE.Vector3()
  const residue = new THREE.Vector3()
  const q = new THREE.Quaternion()
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
    function material(sourceMaterial: THREE.Material) {
      const result = sourceMaterial.clone()
      result.onBeforeCompile = shader => {
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
      result.customProgramCacheKey = () => `native-stock-spring:${stock}`
      return result
    }
    object.material = Array.isArray(object.material) ? object.material.map(material) : material(object.material)
  })
  return {
    length,
    mapPoint(vertex) {
      // Eye/bore anchors are in a rigid end assembly even though their bore
      // centres do not lie on the swept-wire surface used for classification.
      const restEyeX = (restLengthM - source.insideDiameterMm / 1000) / 2
      if (Math.abs(vertex.x) >= restEyeX) {
        vertex.x += Math.sign(vertex.x) * (length.value - restLengthM) / 2
        return
      }
      classify(vertex, coordinates)
      if (Math.abs(coordinates.kind) > 1.5) {
        vertex.x += Math.sign(coordinates.kind) * (length.value - restLengthM) / 2
      } else {
        residue.subVectors(vertex, coordinates.centre)
        oldTangent.copy(coordinates.tangent)
        curve(coordinates.kind, coordinates.t, length.value, centre, tangent)
        q.setFromUnitVectors(oldTangent, tangent)
        vertex.copy(residue.applyQuaternion(q)).add(centre)
      }
    },
  }
}
