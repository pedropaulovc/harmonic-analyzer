import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { MeshoptDecoder } from 'meshoptimizer'
import { BINDINGS, instanceIndex, type Binding } from './bindings'
import { createMechanismInput, createMechanismPose, solveMechanism, MECHANISM_DATA, type MechanismInput, type MechanismPose } from './mechanics'
import { PAPER_FEED_MULTIPLIER, type Gearing } from './kinematics'
import { FULL_FRAME, type CameraPose, type Rect, type TrackView } from './track'

export type InteractionMode = 'following-video' | 'exploring'

export interface Viewer {
  readonly renderer: THREE.WebGLRenderer
  readonly scene: THREE.Scene
  readonly camera: THREE.PerspectiveCamera
  readonly controls: OrbitControls
  resize(): void
  /** Frame the whole machine from the default three-quarter view. */
  fitView(): void
  /** Put the live (exploring) camera exactly at a pose. */
  applyCamera(pose: CameraPose): void
  setInteraction(mode: InteractionMode): void
  /** Draw the live camera into the 16:9 gate. */
  render(): void
  /** Draw each view into its tile of the gate; beforeView poses the machine for it. */
  renderViews(views: readonly TrackView[], beforeView: (view: TrackView) => void): void
}

export interface Machine {
  readonly input: MechanismInput
  readonly pose: MechanismPose
  /** Unresolved bindings or the load failure, for display. */
  readonly missing: readonly string[]
  readonly available: boolean
  update(input: MechanismInput): void
  dispose(): void
}

export type ModelLoadProgress = { phase: 'downloading'; loadedBytes: number; totalBytes: number | null } | { phase: 'preparing' }

const SOURCE_WIDTH = 1920
const SOURCE_HEIGHT = 1080
export const MODEL_URL = `${import.meta.env.BASE_URL}models/ha-harmonic-analyzer.glb`
const Z = new THREE.Vector3(0, 0, 1)
const Y = new THREE.Vector3(0, 1, 0)

const ORBIT_SETTINGS = [
  'enabled', 'minDistance', 'maxDistance', 'minZoom', 'maxZoom', 'minTargetRadius', 'maxTargetRadius',
  'minPolarAngle', 'maxPolarAngle', 'minAzimuthAngle', 'maxAzimuthAngle', 'enableDamping', 'dampingFactor',
  'enableZoom', 'zoomSpeed', 'enableRotate', 'rotateSpeed', 'keyRotateSpeed', 'enablePan', 'panSpeed',
  'screenSpacePanning', 'keyPanSpeed', 'zoomToCursor', 'autoRotate', 'autoRotateSpeed', 'keys', 'mouseButtons',
  'touches', 'zoom0',
] as const satisfies readonly (keyof OrbitControls)[]

/** Cameras and machine points are in the CAD machine frame, metres. */
export function createViewer(canvas: HTMLCanvasElement, onControlsChange: () => void): Viewer {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.autoClear = false
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x11131a)
  // Metallic steel and brass need reflections to read as surfaces.
  const roomEnvironment = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  scene.environment = pmrem.fromScene(roomEnvironment).texture
  roomEnvironment.dispose()
  pmrem.dispose()
  scene.add(new THREE.HemisphereLight(0xffffff, 0x404050, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(2, 3, 2)
  scene.add(key)
  const camera = new THREE.PerspectiveCamera(35, SOURCE_WIDTH / SOURCE_HEIGHT, 0.005, 100)
  camera.position.set(1.2, 1, 1.6)
  // OrbitControls caches camera.up at construction; a rolled camera needs a new instance.
  const controlsUp = camera.up.clone()
  let controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 0.68, 0)
  controls.addEventListener('change', onControlsChange)
  let mode: InteractionMode = 'exploring'

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
    mirrorTarget.setSize(Math.max(1, Math.round(gate.width * renderer.getPixelRatio())), Math.max(1, Math.round(gate.height * renderer.getPixelRatio())))
  }
  addEventListener('resize', resize)

  function writeCamera(pose: CameraPose, width: number, height: number) {
    camera.position.copy(pose.position)
    camera.quaternion.copy(pose.quaternion)
    camera.fov = pose.fov
    camera.aspect = width / height
    const px = pose.principal.x * width, py = pose.principal.y * height
    if (px !== width / 2 || py !== height / 2) camera.setViewOffset(width, height, width / 2 - px, height / 2 - py, width, height)
    else camera.clearViewOffset()
    camera.updateProjectionMatrix()
    camera.updateMatrixWorld(true)
  }

  function syncControlsBasis() {
    if (camera.up.equals(controlsUp)) return
    const previous = controls
    previous.removeEventListener('change', onControlsChange)
    previous.dispose()
    savedPosition.copy(camera.position)
    savedQuaternion.copy(camera.quaternion)
    const next = new OrbitControls(camera, canvas)
    camera.position.copy(savedPosition)
    camera.quaternion.copy(savedQuaternion)
    Object.assign(next, Object.fromEntries(ORBIT_SETTINGS.map(name => [name, previous[name]])))
    next.target.copy(previous.target)
    next.addEventListener('change', onControlsChange)
    controls = next
    controlsUp.copy(camera.up)
  }

  // Orbit about the camera's own up axis so a rolled source camera keeps its roll.
  function rebaseControls() {
    const distance = Math.max(camera.position.distanceTo(controls.target), 0.1)
    forward.set(0, 0, -1).applyQuaternion(camera.quaternion)
    camera.up.set(0, 1, 0).applyQuaternion(camera.quaternion)
    syncControlsBasis()
    controls.target.copy(camera.position).addScaledVector(forward, distance)
    savedPosition.copy(camera.position)
    savedQuaternion.copy(camera.quaternion)
    controls.update()
    camera.position.copy(savedPosition)
    camera.quaternion.copy(savedQuaternion)
    camera.updateMatrixWorld(true)
  }

  function viewport(rect: Rect) {
    const left = gate.x + rect[0] / SOURCE_WIDTH * gate.width
    const top = gate.y + rect[1] / SOURCE_HEIGHT * gate.height
    const w = rect[2] / SOURCE_WIDTH * gate.width
    const h = rect[3] / SOURCE_HEIGHT * gate.height
    const bottom = canvas.clientHeight - top - h
    renderer.setViewport(left, bottom, w, h)
    renderer.setScissor(left, bottom, w, h)
  }

  function drawView(rect: Rect, mirror: boolean) {
    if (mirror) {
      renderer.setRenderTarget(mirrorTarget)
      renderer.setScissorTest(false)
      renderer.clear(true, true, true)
      renderer.render(scene, camera)
      renderer.setRenderTarget(null)
      renderer.setScissorTest(true)
      viewport(rect)
      renderer.clear(true, true, false)
      renderer.render(mirrorScene, mirrorCamera)
    } else {
      renderer.setScissorTest(true)
      viewport(rect)
      renderer.clear(true, true, false)
      renderer.render(scene, camera)
    }
  }

  function beginFrame() {
    renderer.setRenderTarget(null)
    renderer.setScissorTest(false)
    renderer.setViewport(0, 0, canvas.clientWidth, canvas.clientHeight)
    renderer.clear(true, true, true)
  }

  resize()
  return {
    renderer, scene, camera,
    get controls() { return controls },
    resize,
    fitView() {
      bounds.makeEmpty()
      scene.updateWorldMatrix(true, true)
      scene.traverse(node => {
        if (!(node instanceof THREE.Mesh) || !node.visible) return
        if (!node.geometry.boundingBox) node.geometry.computeBoundingBox()
        bounds.union(box.copy(node.geometry.boundingBox!).applyMatrix4(node.matrixWorld))
      })
      if (bounds.isEmpty()) return
      bounds.getCenter(centre)
      bounds.getSize(size)
      camera.fov = 35
      camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
      camera.clearViewOffset()
      const distance = size.length() / 2 / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))
      camera.position.copy(centre).addScaledVector(forward.set(1, 0.25, 1.4).normalize(), distance)
      camera.up.set(0, 1, 0)
      syncControlsBasis()
      controls.target.copy(centre)
      camera.lookAt(centre)
      camera.updateProjectionMatrix()
      controls.update()
    },
    applyCamera(pose) {
      writeCamera(pose, SOURCE_WIDTH, SOURCE_HEIGHT)
      // Orbiting an off-centre projection is disorienting; explore from the centred view.
      camera.clearViewOffset()
      camera.updateProjectionMatrix()
      if (mode === 'exploring') rebaseControls()
    },
    setInteraction(next) {
      if (next === mode) return
      mode = next
      controls.enabled = next === 'exploring'
      if (next === 'exploring') rebaseControls()
    },
    render() {
      beginFrame()
      camera.aspect = SOURCE_WIDTH / SOURCE_HEIGHT
      camera.updateProjectionMatrix()
      drawView(FULL_FRAME, false)
      renderer.setScissorTest(false)
    },
    renderViews(views, beforeView) {
      beginFrame()
      for (const view of views) {
        beforeView(view)
        writeCamera(view.camera, view.rect[2], view.rect[3])
        drawView(view.rect, view.mirror)
      }
      renderer.setScissorTest(false)
    },
  }
}

interface Part {
  path: string
  node: THREE.Object3D
  position: THREE.Vector3
  quaternion: THREE.Quaternion
  scale: THREE.Vector3
  world: THREE.Matrix4
  parentInverse: THREE.Matrix4
  visible: boolean
  binding?: Binding
  station: number
  spring?: { length: { value: number } }
  wireLengthM?: number
  chainStationMm?: number
  chainNextStationMm?: number
  chainRestChordAngleRad?: number
  chainRestCurveM?: THREE.Vector3
}

async function fetchModel(url: string, onProgress?: (progress: ModelLoadProgress) => void): Promise<ArrayBuffer> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Model request returned HTTP ${response.status}`)
  const length = Number(response.headers.get('content-length'))
  // A compressed transfer reports its compressed length, not the decoded bytes.
  const totalBytes = response.headers.get('content-encoding') || !length ? null : length
  if (!onProgress || !response.body) return response.arrayBuffer()
  let loadedBytes = 0
  onProgress({ phase: 'downloading', loadedBytes, totalBytes })
  const counted = response.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      loadedBytes += chunk.byteLength
      onProgress({ phase: 'downloading', loadedBytes, totalBytes })
      controller.enqueue(chunk)
    },
  }))
  return new Response(counted).arrayBuffer()
}

/**
 * Load the release GLB and bind its nodes. A missing model or node is reported
 * in `missing` and never throws: the mechanism still solves (for the force
 * readout) and every bound part that exists still moves.
 */
export async function loadMachine(scene: THREE.Scene, onProgress?: (progress: ModelLoadProgress) => void, url = MODEL_URL): Promise<Machine> {
  const input = createMechanismInput()
  const pose = createMechanismPose()
  const missing: string[] = []
  const parts = new Map<string, Part>()
  const driven: Part[] = []
  let root: THREE.Object3D | null = null

  function addPart(path: string, node: THREE.Object3D): Part {
    const part: Part = {
      path, node, position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone(),
      world: node.matrixWorld.clone(), parentInverse: node.parent!.matrixWorld.clone().invert(), visible: node.visible, station: -1,
    }
    parts.set(path, part)
    return part
  }

  try {
    const buffer = await fetchModel(url, onProgress)
    onProgress?.({ phase: 'preparing' })
    await MeshoptDecoder.ready
    const gltf = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).parseAsync(buffer, new URL('.', new URL(url, location.href)).href)
    const loaded = gltf.scene
    loaded.updateMatrixWorld(true)
    const visit = (node: THREE.Object3D, parentPath: string) => {
      const name = typeof node.userData.name === 'string' ? node.userData.name : node.name
      const path = parentPath ? `${parentPath}/${name}` : name
      if (node !== loaded) addPart(path, node)
      for (const child of node.children) visit(child, node === loaded ? '' : path)
    }
    visit(loaded, '')
    for (const binding of BINDINGS) {
      let resolved = 0
      const stations = new Set<number>()
      for (const part of parts.values()) {
        if (!binding.pattern.test(part.path)) continue
        resolved++
        part.binding = binding
        if (binding.kind === 'indexed') stations.add(part.station = instanceIndex(part.path, binding.pattern) - 1)
        if (binding.motion !== 'paper-sprocket') driven.push(part)
        if (binding.motion === 'lever-wire' || binding.motion === 'pen-wire') part.wireLengthM = wireLength(part.node)
        if (binding.motion === 'channel-spring' || binding.motion === 'counter-spring') {
          const counter = binding.motion === 'counter-spring'
          const restLengthMm = counter ? MECHANISM_DATA.counter.nativeReference.length_mm : MECHANISM_DATA.restChannels[part.station]?.nativeSpring.length_mm
          if (restLengthMm === undefined) missing.push(`${part.path}: no rest spring length`)
          else part.spring = createSpringDeformer(part.node, restLengthMm / 1000, counter ? 'counter' : 'channel')
        }
      }
      if (resolved !== binding.expected) missing.push(`${binding.id}: resolved ${resolved}/${binding.expected}`)
      if (binding.kind === 'indexed') for (let station = 0; station < 20; station++) {
        if (!stations.has(station)) missing.push(`${binding.id}: missing station ${station + 1}`)
      }
    }
    scene.add(loaded)
    root = loaded
  } catch (error) {
    parts.clear()
    driven.length = 0
    missing.push(`model unavailable: ${error instanceof Error ? error.message : String(error)}`)
  }
  if (missing.length) console.warn(`[machine] unresolved:\n${missing.join('\n')}`)

  const a = new THREE.Vector3()
  const b = new THREE.Vector3()
  const c = new THREE.Vector3()
  const pivot = new THREE.Vector3()
  const axis = new THREE.Vector3()
  const origin = new THREE.Vector3()
  const restAnchor = new THREE.Vector3()
  const quaternion = new THREE.Quaternion()
  const rotation = new THREE.Matrix4()
  const delta = new THREE.Matrix4()
  const swing = new THREE.Matrix4()
  const desired = new THREE.Matrix4()
  const local = new THREE.Matrix4()
  const knife = new THREE.Vector3().fromArray(MECHANISM_DATA.summing.knifeMm).multiplyScalar(0.001)
  const crankPart = parts.get('ha-harmonic-analyzer/dt-drive-train/dt-crankshaft-1')
  const conePart = parts.get('ha-harmonic-analyzer/dt-drive-train/dt-cone-gear-shaft-1')
  const crankPivot = crankPart ? new THREE.Vector3().setFromMatrixPosition(crankPart.world) : new THREE.Vector3()
  const conePivot = conePart ? new THREE.Vector3().setFromMatrixPosition(conePart.world) : new THREE.Vector3()
  const coneAxis = conePart ? new THREE.Vector3().setFromMatrixColumn(conePart.world, 2).normalize() : new THREE.Vector3(0, 0, 1)
  const paperKnobPart = parts.get('ha-harmonic-analyzer/pd-paper-drive/pd-transgear-knob-shaft-1')
  const paperFeedPart = parts.get('ha-harmonic-analyzer/pd-paper-drive/pd-rack-pinion-1')
  const paperKnobRotation = new THREE.Matrix4()
  const paperFeedRotation = new THREE.Matrix4()
  const chain = MECHANISM_DATA.paperDrive.chain

  // Chain links: find each link's rest station on the rest (small-large) centreline.
  const links = driven.filter(part => part.binding!.motion === 'chain-link')
  if (links.length) {
    const step = 0.05
    const samples = Math.ceil(chain.centrelineLengthMm / step)
    const curve = new Float64Array(samples * 2)
    for (let i = 0; i < samples; i++) {
      chainPoint(i * step, 'small-large', a)
      curve[i * 2] = a.x
      curve[i * 2 + 1] = a.y
    }
    for (const link of links) {
      restAnchor.setFromMatrixPosition(link.world)
      let best = Infinity
      for (let i = 0; i < samples; i++) {
        const d = (curve[i * 2]! - restAnchor.x) ** 2 + (curve[i * 2 + 1]! - restAnchor.y) ** 2
        if (d < best) { best = d; link.chainStationMm = i * step }
      }
    }
    links.sort((left, right) => left.chainStationMm! - right.chainStationMm!)
    links.forEach((link, i) => {
      link.chainNextStationMm = links[(i + 1) % links.length]!.chainStationMm
      link.chainRestCurveM = chainPoint(link.chainStationMm!, 'small-large', new THREE.Vector3())
      chainPoint(link.chainNextStationMm!, 'small-large', b)
      link.chainRestChordAngleRad = Math.atan2(b.y - link.chainRestCurveM.y, b.x - link.chainRestCurveM.x)
    })
  }

  // Removable sprockets: T24 upper, T12 crank, and a T18 spare cloned onto both seats for medium-medium.
  const upperSprocket = parts.get('ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-1')
  const crankSprocket = parts.get('ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-2')
  const spareSprocket = parts.get('ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-3')
  const mediumClone = (seat: string) => {
    if (!spareSprocket) return undefined
    const node = spareSprocket.node.clone(true)
    spareSprocket.node.parent!.add(node)
    node.visible = false
    return addPart(`${spareSprocket.path}@${seat}`, node)
  }
  const upperMedium = mediumClone('upper')
  const crankMedium = mediumClone('crank')

  function around(out: THREE.Matrix4, centre: THREE.Vector3, direction: THREE.Vector3, angle: number) {
    quaternion.setFromAxisAngle(direction, angle)
    out.makeRotationFromQuaternion(quaternion)
    a.copy(centre).applyMatrix4(out)
    out.setPosition(centre.x - a.x, centre.y - a.y, centre.z - a.z)
  }
  function setWorld(part: Part, world: THREE.Matrix4) {
    local.multiplyMatrices(part.parentInverse, world)
    local.decompose(part.node.position, part.node.quaternion, part.node.scale)
  }
  function rotate(part: Part, centre: THREE.Vector3, direction: THREE.Vector3, angle: number, outer?: THREE.Matrix4) {
    around(delta, centre, direction, angle)
    desired.multiplyMatrices(delta, part.world)
    if (outer) desired.premultiply(outer)
    setWorld(part, desired)
  }
  function translate(part: Part, x: number, y: number, z: number) {
    desired.copy(part.world)
    desired.elements[12]! += x; desired.elements[13]! += y; desired.elements[14]! += z
    setWorld(part, desired)
  }
  /** Rotate a rigid member about its mechanical support point and move that point. */
  function endpoint(part: Part, restPoint: THREE.Vector3, newPoint: THREE.Vector3, angle: number) {
    around(delta, restPoint, Z, angle)
    delta.elements[12]! += newPoint.x - restPoint.x
    delta.elements[13]! += newPoint.y - restPoint.y
    delta.elements[14]! += newPoint.z - restPoint.z
    desired.multiplyMatrices(delta, part.world)
    setWorld(part, desired)
  }

  function placeSpring(part: Part, lower: THREE.Vector3, upper: THREE.Vector3, clocking: number) {
    origin.addVectors(lower, upper).multiplyScalar(0.5)
    axis.subVectors(upper, lower).normalize()
    // Local +X along the loaded eyes, +Y along ±world Z, keeping the hook clocking.
    desired.makeBasis(axis, b.set(0, 0, clocking), c.set(clocking * axis.y, -clocking * axis.x, 0))
    desired.setPosition(origin)
    setWorld(part, desired)
  }

  function alignWire(part: Part, endpoints: ArrayLike<number>) {
    // Wire cylinders run along local +Y from their origin; stretch +Y only.
    origin.set(endpoints[3]!, endpoints[4]!, endpoints[5]!)
    axis.set(endpoints[0]!, endpoints[1]!, endpoints[2]!).sub(origin)
    const length = axis.length()
    axis.divideScalar(length)
    quaternion.setFromUnitVectors(b.setFromMatrixColumn(part.world, 1).normalize(), axis)
    rotation.makeRotationFromQuaternion(quaternion)
    desired.copy(part.world)
    const stretch = length / part.wireLengthM!
    desired.elements[4]! *= stretch
    desired.elements[5]! *= stretch
    desired.elements[6]! *= stretch
    desired.premultiply(rotation)
    desired.setPosition(origin)
    setWorld(part, desired)
  }

  function chainPoint(stationMm: number, gearing: Gearing, out: THREE.Vector3): THREE.Vector3 {
    const path = chain.paths[gearing]
    const knobCentre = chain.knobCentrePreMirrorMm
    let distance = ((stationMm % chain.centrelineLengthMm) + chain.centrelineLengthMm) % chain.centrelineLengthMm
    for (const arc of path.arcsMm) {
      const arcLength = arc[2]! * arc[4]!
      if (distance <= arcLength) {
        const angle = arc[3]! + distance / arc[2]!
        return out.set(-(arc[0]! + arc[2]! * Math.cos(angle) + knobCentre[0]!) / 1000, (arc[1]! + arc[2]! * Math.sin(angle) + knobCentre[1]!) / 1000, 0)
      }
      distance -= arcLength
    }
    const line = path.tautMm
    const t = distance / path.tautLengthMm
    return out.set(-(line[0]! + t * (line[2]! - line[0]!) + knobCentre[0]!) / 1000, (line[1]! + t * (line[3]! - line[1]!) + knobCentre[1]!) / 1000, 0)
  }

  function driveChainLink(part: Part) {
    if (part.chainStationMm === undefined) return
    // Links follow the planar centreline; tooth contact and chain slack are not solved.
    const advance = -chain.paths[input.gearing].crankPitchRadiusMm * pose.crankAngleRad
    chainPoint(part.chainStationMm + advance, input.gearing, origin)
    chainPoint(part.chainNextStationMm! + advance, input.gearing, b)
    const angle = Math.atan2(b.y - origin.y, b.x - origin.x)
    restAnchor.setFromMatrixPosition(part.world)
    origin.sub(part.chainRestCurveM!).add(restAnchor)
    endpoint(part, restAnchor, origin, angle - part.chainRestChordAngleRad!)
  }

  function sprocketAt(part: Part, frame: Part, angle: number) {
    desired.copy(frame.world)
    pivot.setFromMatrixPosition(desired)
    around(delta, pivot, Z, angle)
    desired.premultiply(delta)
    if (frame === crankSprocket) desired.premultiply(swing)
    setWorld(part, desired)
    part.node.visible = true
  }

  function driveSprockets(knobAngle: number) {
    if (!upperSprocket || !crankSprocket || !spareSprocket || !upperMedium || !crankMedium) return
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

  function update(source: MechanismInput) {
    if (source !== input) {
      input.crankTurns = source.crankTurns
      input.amplitudes.set(source.amplitudes)
      input.phases.set(source.phases)
      input.gearing = source.gearing
      input.magnification = source.magnification
      Object.assign(input.setup, source.setup)
    }
    solveMechanism(input, pose)
    if (!root) return
    for (const part of parts.values()) {
      part.node.position.copy(part.position)
      part.node.quaternion.copy(part.quaternion)
      part.node.scale.copy(part.scale)
      part.node.visible = part.visible
    }
    pivot.fromArray(pose.setup.coneSwingPivotM)
    around(swing, pivot, Y, pose.setup.coneSwingRad)
    const paper = MECHANISM_DATA.paperDrive
    const knobAngle = pose.crankAngleRad * paper.chainRatioFine * PAPER_FEED_MULTIPLIER[input.gearing]
    const feedAngle = knobAngle * paper.externalMeshSense * paper.reducerRatio
    // Knob and feed groups turn about their shared world-Z axes, not each part origin.
    if (paperKnobPart) around(paperKnobRotation, pivot.setFromMatrixPosition(paperKnobPart.world), Z, knobAngle)
    if (paperFeedPart) around(paperFeedRotation, pivot.setFromMatrixPosition(paperFeedPart.world), Z, feedAngle)
    const channel = MECHANISM_DATA.channel
    for (const part of driven) {
      const j = part.station
      const p = j * 3
      switch (part.binding!.motion) {
        case 'crank': rotate(part, crankPivot, Z, pose.crankAngleRad, swing); break
        case 'cone-spin': rotate(part, conePivot, coneAxis, pose.coneShaftAngleRad, swing); break
        case 'cone-swing': desired.multiplyMatrices(swing, part.world); setWorld(part, desired); break
        case 'cylinder':
          pivot.set(channel.camShaftMm[0]! / 1000, channel.camShaftMm[1]! / 1000, part.world.elements[14]!)
          rotate(part, pivot, Z, pose.channelAnglesRad[j]!); break
        case 'rocker':
          pivot.set(channel.pivotMm[0]! / 1000, channel.pivotMm[1]! / 1000, part.world.elements[14]!)
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
          pivot.set(channel.fulcrumMm[0]! / 1000, channel.fulcrumMm[1]! / 1000, part.world.elements[14]!)
          // Remove the authored rest tilt before applying the solved tilt.
          rotate(part, pivot, Z, pose.leverAnglesRad[j]! - Math.atan2(-part.world.elements[1]!, -part.world.elements[0]!)); break
        case 'channel-spring':
          if (!part.spring) break
          a.fromArray(pose.springLowerM, p); b.fromArray(pose.springUpperM, p)
          part.spring.length.value = pose.springLengthsM[j]!
          placeSpring(part, a, b, 1); break
        case 'counter-spring':
          if (!part.spring) break
          a.fromArray(pose.counter.lowerM); b.fromArray(pose.counter.upperM)
          part.spring.length.value = pose.counter.lengthM
          placeSpring(part, a, b, -1); break
        case 'summing': case 'magnifier-fixed': rotate(part, knife, Z, pose.summingAngleRad); break
        case 'gooseneck': translate(part, 0, pose.counter.gooseneckHeightM - MECHANISM_DATA.counter.nativeGooseneckYMm / 1000, 0); break
        case 'magnifier-clamp': case 'magnifier-rod': case 'magnifier-fixture': {
          const change = input.magnification * MECHANISM_DATA.summing.anchorArmMm / 1000 - MECHANISM_DATA.magnifier.clampRadiusBandMm[1]! / 1000
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
        case 'lever-wire': alignWire(part, pose.magnifier.leverWirePathM); break
        case 'pen-wire': alignWire(part, pose.magnifier.penWirePathM); break
        case 'pen': translate(part, 0, pose.magnifier.penTravelM, 0); break
        case 'platen': translate(part, pose.platenTravelM, 0, 0); break
        case 'pinion-swing': rotate(part, pivot.fromArray(pose.setup.pinionPivotM), Z, pose.setup.pinionSwingRad); break
        case 'pinion-cam': case 'pinion-lever': rotate(part, pivot.fromArray(pose.setup.pinionLiftAxisM), Z, pose.setup.pinionCamRad); break
        case 'paper-knob': desired.multiplyMatrices(paperKnobRotation, part.world); setWorld(part, desired); break
        case 'paper-feed': desired.multiplyMatrices(paperFeedRotation, part.world); setWorld(part, desired); break
        case 'chain-link': driveChainLink(part); break
      }
    }
    driveSprockets(knobAngle)
    root.updateMatrixWorld(true)
  }

  return {
    input, pose, missing,
    get available() { return root !== null },
    update,
    dispose() {
      if (!root) return
      root.removeFromParent()
      root.traverse(node => {
        if (!(node instanceof THREE.Mesh)) return
        node.geometry.dispose()
        for (const material of Array.isArray(node.material) ? node.material : [node.material]) material.dispose()
      })
      root = null
    },
  }
}

function wireLength(node: THREE.Object3D): number {
  let length = 0
  node.traverse(child => {
    if (!(child instanceof THREE.Mesh)) return
    child.geometry.computeBoundingBox()
    length = Math.max(length, child.geometry.boundingBox!.max.y - child.geometry.boundingBox!.min.y)
  })
  return length
}

interface SpringCoordinates { kind: number; t: number; centre: THREE.Vector3; tangent: THREE.Vector3 }

/**
 * Stretch the GLB's own swept-wire spring mesh (no replacement tube): hooks and
 * transitions move rigidly, the coil's pitch follows the length uniform. Each
 * vertex is classified once at load; the frame loop only sets `length.value`.
 * Coil and vendor-transition constants: ch/sm spring stock geometry in cad/scripts.
 */
function createSpringDeformer(node: THREE.Object3D, restLengthM: number, stock: 'channel' | 'counter') {
  const length = { value: restLengthM }
  const rest = { value: restLengthM }
  const counter = stock === 'counter'
  const source = counter ? MECHANISM_DATA.counter : MECHANISM_DATA.spring
  const radius = (source.coilOutsideDiameterMm - source.wireDiameterMm) / 2000
  const wireRadius = source.wireDiameterMm / 2000
  const turns = source.coilTurns
  const inset = counter ? 0.0102997 : source.insideDiameterMm / 1000
  const endCorrection = counter ? wireRadius : 0
  const residue = new THREE.Vector3()
  const trial = new THREE.Vector3()
  const trialTangent = new THREE.Vector3()

  // The transition is the vendor's clamped cubic, in metres.
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
    // End loops and transitions are rigid end assemblies; only the coil stretches.
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
      for (let n = 0; n < 6; n++) {
        curve(0, t, restLengthM, trial, trialTangent)
        residue.subVectors(vertex, trial)
        t = Math.min(1, Math.max(0, t + residue.dot(trialTangent) / Math.hypot(height, radius * turns * 2 * Math.PI)))
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
      const side = vertex.x < 0 ? -1 : 1
      const eyeX = side * (restLengthM - source.insideDiameterMm / 1000) / 2
      const hookDistance = (Math.hypot(vertex.x - eyeX, vertex.y) - radius) ** 2 + vertex.z * vertex.z
      if (side * (vertex.x - eyeX) >= 0 && hookDistance < best) {
        best = hookDistance
        result.kind = side * 2
        result.centre.copy(vertex); result.tangent.set(1, 0, 0)
      }
      let chosenT = 0
      let curveDistance = Infinity
      for (let sample = 0; sample <= 32; sample++) {
        curve(side, sample / 32, restLengthM, trial, trialTangent)
        const distance = vertex.distanceToSquared(trial)
        if (distance < curveDistance) { curveDistance = distance; chosenT = sample / 32 }
      }
      let lo = Math.max(0, chosenT - 1 / 32)
      let hi = Math.min(1, chosenT + 1 / 32)
      for (let n = 0; n < 18; n++) {
        const left = lo + (hi - lo) * 0.3819660112501051
        const right = hi - (hi - lo) * 0.3819660112501051
        curve(side, left, restLengthM, trial, trialTangent)
        const dl = vertex.distanceToSquared(trial)
        curve(side, right, restLengthM, trial, trialTangent)
        if (dl < vertex.distanceToSquared(trial)) hi = right; else lo = left
      }
      const t = (lo + hi) / 2
      curve(side, t, restLengthM, trial, trialTangent)
      if (vertex.distanceToSquared(trial) < best) {
        result.kind = side; result.t = t
        result.centre.copy(trial); result.tangent.copy(trialTangent)
      }
    }
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
  const deformed = (material: THREE.Material) => {
    const result = material.clone()
    result.onBeforeCompile = shader => {
      shader.uniforms.springLength = length
      shader.uniforms.springRestLength = rest
      shader.vertexShader = (shaderFunctions + shader.vertexShader)
        .replace('#include <beginnormal_vertex>', `#include <beginnormal_vertex>
vec3 springNewCentre;
vec3 springNewTangent;
springCurve(springNewCentre, springNewTangent);
objectNormal = springTurn(objectNormal, springRestTangent, springNewTangent);`)
        .replace('#include <begin_vertex>', 'vec3 transformed = springNewCentre + springTurn(position - springRestCentre, springRestTangent, springNewTangent);')
    }
    result.customProgramCacheKey = () => `stock-spring:${stock}`
    return result
  }
  const point = new THREE.Vector3()
  const coordinates: SpringCoordinates = { kind: 0, t: 0, centre: new THREE.Vector3(), tangent: new THREE.Vector3() }
  node.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    const geometry = object.geometry.clone()
    const position = geometry.getAttribute('position')
    const parameters = new Float32Array(position.count * 2)
    const centres = new Float32Array(position.count * 3)
    const tangents = new Float32Array(position.count * 3)
    for (let i = 0; i < position.count; i++) {
      classify(point.fromBufferAttribute(position, i), coordinates)
      parameters[i * 2] = coordinates.kind; parameters[i * 2 + 1] = coordinates.t
      coordinates.centre.toArray(centres, i * 3)
      coordinates.tangent.toArray(tangents, i * 3)
    }
    geometry.setAttribute('springCoordinate', new THREE.BufferAttribute(parameters, 2))
    geometry.setAttribute('springRestCentre', new THREE.BufferAttribute(centres, 3))
    geometry.setAttribute('springRestTangent', new THREE.BufferAttribute(tangents, 3))
    object.geometry = geometry
    // The shader moves vertices outside the rest bounding volume.
    object.frustumCulled = false
    object.material = Array.isArray(object.material) ? object.material.map(deformed) : deformed(object.material)
  })
  return { length }
}
