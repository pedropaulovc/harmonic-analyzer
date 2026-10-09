import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { BINDINGS, instanceIndex, type Binding, type Motion } from '../bindings'
import { CHANNELS, channelAngle, physicalChannelAngle, MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_MAX } from '../kinematics'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput, type SerializedMechanismInput } from '../mechanics'
import { loadMachine, type Machine, type CameraRecord, type Presentation, type Point3 } from '../scene'

export interface FitRequest {
  camera: CameraRecord
  input: SerializedMechanismInput
  width: number
  height: number
  presentation: Presentation
  groups?: string[]
  /** Optional appearance passes; IDs are always returned. */
  outputs?: ('rgb' | 'worldPositions')[]
}
export interface FitRender {
  width: number
  height: number
  ids: string
  dtype: 'uint8' | 'uint16'
  /** sRGB uint8 RGB, top-left row-major, background matches the companion. */
  rgb?: string
  /** Little-endian float32 XYZ in native metres; all three components NaN off-machine. */
  worldPositions?: string
}
export interface FitBounds { min: Point3; max: Point3 }
export interface FitTimings {
  renders: number
  solveMs: number
  drawMs: number
  readbackMs: number
  encodeMs: number
  batchMs: number
}
export interface FitReady {
  partPaths: string[]
  groups: Record<string, string[]>
  groupIds: Record<string, number>
  channelMapping: { physicalInstance: number; inputIndex: number; harmonic: number; radiansPerCrankTurn: number; evidence: string }[]
  /** Bounds at the default MechanismInput used during readiness, in native metres. */
  boundsMetres: FitBounds
  groupBoundsMetres: Record<string, FitBounds>
  renderer: { renderer: string; vendor: string; version: string }
  timings: FitTimings
}
export interface HarmonicFit {
  ready(): Promise<FitReady>
  render(request: FitRequest): Promise<FitRender>
  renderBatch(requests: FitRequest[]): Promise<FitRender[]>
}
declare global { interface Window { harmonicFit: HarmonicFit } }

const groupNames = [
  'static', 'crank', 'cones', ...Array.from({ length: CHANNELS }, (_, i) => `channel-${i + 1}`),
  'amplitude-bars', 'summing', 'magnifier', 'wheel-wire', 'pen', 'platen-paper', 'springs',
]
const groupIds = Object.fromEntries(groupNames.map((name, i) => [name, i + 1]))
const channelMapping = Array.from({ length: CHANNELS }, (_, inputIndex) => {
  const radiansPerCrankTurn = physicalChannelAngle(1, inputIndex)
  const harmonic = Array.from({ length: CHANNELS }, (_, k) => k + 1)
    .find(k => Math.abs(channelAngle(1, k) - radiansPerCrankTurn) < 1e-12)
  if (harmonic === undefined) throw new Error(`No harmonic for physical input ${inputIndex}`)
  return {
    physicalInstance: inputIndex + 1, inputIndex, harmonic, radiansPerCrankTurn,
    evidence: 'scene.ts: part.station=instanceIndex(part.path,binding.pattern)-1 indexes pose; mechanics.ts: solveChannel(physicalChannelAngle(driveTurns,j)+phases[j],j,pose), amplitudes[j] in physical station order; kinematics.ts: physicalChannelAngle(turns,j)=channelAngle(turns,CHANNELS-j)',
  }
})
const motionGroups: Partial<Record<Motion, string>> = {
  crank: 'crank', 'cone-spin': 'cones', 'cone-swing': 'cones',
  'pinion-swing': 'cones', 'pinion-cam': 'cones', 'pinion-lever': 'cones',
  bar: 'amplitude-bars', summing: 'summing', gooseneck: 'summing',
  'magnifier-fixed': 'magnifier', 'magnifier-clamp': 'magnifier',
  'magnifier-rod': 'magnifier', 'magnifier-fixture': 'magnifier',
  wheel: 'wheel-wire', 'lever-wire': 'wheel-wire', 'pen-wire': 'wheel-wire', pen: 'pen',
  platen: 'platen-paper', 'paper-knob': 'platen-paper', 'paper-feed': 'platen-paper',
  'paper-sprocket': 'platen-paper', 'chain-link': 'platen-paper',
  'channel-spring': 'springs', 'counter-spring': 'springs',
}

const canvas = document.querySelector<HTMLCanvasElement>('#fit')!
const status = document.querySelector<HTMLParagraphElement>('#status')!
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false })
renderer.setPixelRatio(1)
renderer.outputColorSpace = THREE.LinearSRGBColorSpace
renderer.toneMapping = THREE.NoToneMapping
renderer.setClearColor(0, 0)
const scene = new THREE.Scene()
const camera = new THREE.PerspectiveCamera(30, 16 / 9, 0.001, 100)
const target = new THREE.WebGLRenderTarget(480, 270, {
  minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
  format: THREE.RGBAFormat, type: THREE.UnsignedByteType,
  depthBuffer: true, stencilBuffer: false,
})
target.texture.colorSpace = THREE.NoColorSpace
let rgba = new Uint8Array(480 * 270 * 4)
const bytesPerId = groupNames.length <= 255 ? 1 : 2
let encoded = new Uint8Array(480 * 270 * bytesPerId)
const input = createMechanismInput()
let machine: Machine
let inputSolved = false
const setupKeys = Object.keys(input.setup) as (keyof MechanismInput['setup'])[]
const timings: FitTimings = { renders: 0, solveMs: 0, drawMs: 0, readbackMs: 0, encodeMs: 0, batchMs: 0 }

type Drawable = THREE.Mesh | THREE.Line | THREE.Points
type MaterialSet = THREE.Material | THREE.Material[]
interface FitDrawable {
  path: string
  object: Drawable
  group: string
  nativeMaterial: MaterialSet
  idMaterial: MaterialSet
  worldMaterial?: MaterialSet
}
const drawables: FitDrawable[] = []
let lightingReady = false
let rgbBytes = new Uint8Array(0)
let worldTarget: THREE.WebGLRenderTarget | undefined
let worldRgba = new Float32Array(0)
let worldXyz = new Float32Array(0)

function bindingFor(path: string): { binding: Binding; path: string } | undefined {
  for (let candidate = path; candidate; candidate = candidate.slice(0, candidate.lastIndexOf('/'))) {
    const binding = BINDINGS.find(item => item.pattern.test(candidate))
    if (binding) return { binding, path: candidate }
    if (!candidate.includes('/')) break
  }
  return undefined
}

// Collect original CAD names exactly as loadMachine does, including native spare instances.
function collect(node: THREE.Object3D, parentPath: string): void {
  const name = typeof node.userData.name === 'string' ? node.userData.name : node.name
  const instancePath: unknown = node.userData.nativeInstancePath
  const path = typeof instancePath === 'string' ? instancePath : parentPath ? `${parentPath}/${name}` : name
  if (node instanceof THREE.Mesh || node instanceof THREE.Line || node instanceof THREE.Points) {
    const sourcePath: unknown = node.userData.nativeInstanceSource
    const bound = bindingFor(typeof sourcePath === 'string' ? sourcePath : path)
    let group: string | undefined
    if (bound && ['cylinder', 'rod', 'rocker', 'lever'].includes(bound.binding.motion)) {
      const mapping = channelMapping[instanceIndex(bound.path, bound.binding.pattern) - 1]
      if (!mapping) throw new Error(`Invalid physical station: ${path}`)
      group = `channel-${mapping.harmonic}`
    } else if (bound) group = motionGroups[bound.binding.motion]
    drawables.push({ path, object: node, group: group ?? 'static', nativeMaterial: node.material, idMaterial: node.material })
  }
  for (const child of node.children) collect(child, path)
}

// Retain the native vertex hook (notably spring swept-wire deformation) while
// replacing only the output with exact, unlit RG ID bytes. No lighting, alpha,
// colour conversion, tone mapping, blending or multisampling enters the ID pass.
function idMaterial(source: THREE.Material, id: number): THREE.MeshBasicMaterial {
  const result = new THREE.MeshBasicMaterial({ side: source.side, toneMapped: false, blending: THREE.NoBlending })
  const nativeCompile = source.onBeforeCompile
  const nativeKey = source.customProgramCacheKey()
  result.onBeforeCompile = (shader, activeRenderer) => {
    // The native spring hook declares its curve in beginnormal_vertex. Basic
    // normally omits that stage without an envmap; make it available to the hook.
    shader.vertexShader = shader.vertexShader.replace('#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )', '#if 1')
    nativeCompile.call(source, shader, activeRenderer)
    shader.uniforms.fitId = { value: new THREE.Vector3((id & 255) / 255, (id >>> 8) / 255, 0) }
    shader.fragmentShader = 'uniform vec3 fitId;\nvoid main() { gl_FragColor = vec4(fitId, 1.0); }'
  }
  result.customProgramCacheKey = () => `fit-id:${nativeKey}`
  return result
}

function worldMaterial(source: THREE.Material): THREE.MeshBasicMaterial {
  const result = new THREE.MeshBasicMaterial({ side: source.side, toneMapped: false, blending: THREE.NoBlending })
  const nativeCompile = source.onBeforeCompile
  const nativeKey = source.customProgramCacheKey()
  result.onBeforeCompile = (shader, activeRenderer) => {
    shader.vertexShader = shader.vertexShader.replace('#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )', '#if 1')
    nativeCompile.call(source, shader, activeRenderer)
    shader.vertexShader = 'varying vec3 fitWorldPosition;\n' + shader.vertexShader
    shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', `
#include <project_vertex>
fitWorldPosition = (modelMatrix * vec4(transformed, 1.0)).xyz;
`)
    shader.fragmentShader = 'varying vec3 fitWorldPosition;\nvoid main() { gl_FragColor = vec4(fitWorldPosition, 1.0); }'
  }
  result.customProgramCacheKey = () => `fit-world:${nativeKey}`
  return result
}

function prepareLighting(): void {
  if (lightingReady) return
  // Same environment and light settings as createViewer in scene.ts. The
  // environment geometry supplies reflections only and is never added here.
  const room = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  try { scene.environment = pmrem.fromScene(room).texture }
  finally { room.dispose(); pmrem.dispose() }
  scene.add(new THREE.HemisphereLight(0xffffff, 0x404050, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(2, 3, 2)
  scene.add(key)
  lightingReady = true
}

function renderAppearance(request: FitRequest, result: FitRender): void {
  const { width, height } = request
  const mirror = request.presentation === 'horizontal-mirror'
  try {
    if (request.outputs?.includes('rgb')) {
      prepareLighting()
      for (const item of drawables) item.object.material = item.nativeMaterial
      renderer.outputColorSpace = THREE.SRGBColorSpace
      if (canvas.width !== width || canvas.height !== height) renderer.setSize(width, height, false)
      scene.background = new THREE.Color(0x11131a)
      renderer.setRenderTarget(null)
      renderer.render(scene, camera)
      const gl = renderer.getContext()
      gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, rgba)
      if (rgbBytes.length !== width * height * 3) rgbBytes = new Uint8Array(width * height * 3)
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const source = ((height - 1 - y) * width + (mirror ? width - 1 - x : x)) * 4
        const destination = (y * width + x) * 3
        rgbBytes[destination] = rgba[source]!
        rgbBytes[destination + 1] = rgba[source + 1]!
        rgbBytes[destination + 2] = rgba[source + 2]!
      }
      result.rgb = base64(rgbBytes)
    }
    scene.background = null
    renderer.outputColorSpace = THREE.LinearSRGBColorSpace
    if (request.outputs?.includes('worldPositions')) {
      if (!worldTarget) {
        if (!renderer.getContext().getExtension('EXT_color_buffer_float')) throw new Error('World-position rendering requires EXT_color_buffer_float')
        worldTarget = new THREE.WebGLRenderTarget(width, height, {
          minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
          format: THREE.RGBAFormat, type: THREE.FloatType, depthBuffer: true, stencilBuffer: false,
        })
        worldTarget.texture.colorSpace = THREE.NoColorSpace
      }
      if (worldTarget.width !== width || worldTarget.height !== height) worldTarget.setSize(width, height)
      if (worldRgba.length !== width * height * 4) {
        worldRgba = new Float32Array(width * height * 4)
        worldXyz = new Float32Array(width * height * 3)
      }
      for (const item of drawables) {
        if (!item.worldMaterial) item.worldMaterial = Array.isArray(item.nativeMaterial)
          ? item.nativeMaterial.map(worldMaterial) : worldMaterial(item.nativeMaterial)
        item.object.material = item.worldMaterial
      }
      renderer.setRenderTarget(worldTarget)
      renderer.render(scene, camera)
      renderer.readRenderTargetPixels(worldTarget, 0, 0, width, height, worldRgba)
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const pixel = y * width + x
        const destination = pixel * 3
        const idOffset = pixel * bytesPerId
        if (encoded[idOffset] === 0 && (bytesPerId === 1 || encoded[idOffset + 1] === 0)) {
          worldXyz[destination] = worldXyz[destination + 1] = worldXyz[destination + 2] = NaN
        } else {
          const source = ((height - 1 - y) * width + (mirror ? width - 1 - x : x)) * 4
          worldXyz[destination] = worldRgba[source]!
          worldXyz[destination + 1] = worldRgba[source + 1]!
          worldXyz[destination + 2] = worldRgba[source + 2]!
        }
      }
      result.worldPositions = base64(new Uint8Array(worldXyz.buffer))
    }
  } finally {
    renderer.setRenderTarget(null)
    renderer.outputColorSpace = THREE.LinearSRGBColorSpace
    scene.background = null
    for (const item of drawables) item.object.material = item.idMaterial
  }
}

function probeInput(seed: number): MechanismInput {
  const probe = createMechanismInput()
  probe.crankTurns = seed === 1 ? 3.173 : -1.419
  for (let j = 0; j < CHANNELS; j++) {
    probe.amplitudes[j] = (j % 2 ? -1 : 1) * (seed === 1 ? 0.45 : 0.23)
    probe.phases[j] = (j + 1) * (seed === 1 ? 0.17 : -0.31)
  }
  probe.gearing = seed === 1 ? 'large-small' : 'medium-medium'
  probe.magnification = seed === 1 ? MAGNIFIER_RATIO_MIN : MAGNIFIER_RATIO_MAX
  probe.setup.platenOffsetM = seed === 1 ? 0.013 : -0.009
  probe.setup.wireFixtureOffsetM = seed === 1 ? 0.001 : -0.001
  probe.setup.coneSwingRad = MECHANISM_DATA.setup.coneDisengageRad * (seed === 1 ? 1 : 0.4)
  probe.setup.pinionCamRad = MECHANISM_DATA.setup.pinionEngageCamRad * (seed === 1 ? 1 : 0.4)
  probe.setup.heldChannelTurns = seed === 1 ? 2.13 : -3.17
  probe.setup.driveCrankOffsetTurns = 0.41
  return probe
}

const loaded = (async (): Promise<FitReady> => {
  machine = await loadMachine(scene)
  if (machine.availability !== 'available') throw new Error(machine.loadError ?? 'Native GLB unavailable')
  // loadMachine adds one GLTF scene wrapper, whose name is not a native path.
  for (const root of scene.children) for (const child of root.children) collect(child, '')
  const nativePaths = new Set(machine.nativeDrawablePartPaths)
  if (drawables.length !== nativePaths.size || drawables.some(item => !nativePaths.has(item.path))) {
    throw new Error('Fit render inventory does not match native drawable paths')
  }
  machine.update(input) // Calls solveMechanism and applies its real native geometry pose.
  const baseline = drawables.map(item => item.object.matrixWorld.clone())
  for (const seed of [1, 2]) {
    const probe = probeInput(seed)
    machine.update(probe)
    // Also exercise the engaged-bank crank drive; the first probe is disengaged.
    for (const coneSwingRad of [probe.setup.coneSwingRad, 0]) {
      probe.setup.coneSwingRad = coneSwingRad
      machine.update(probe)
      for (let i = 0; i < drawables.length; i++) {
        const item = drawables[i]!
        if (item.group !== 'static') continue
        const reference = baseline[i]!.elements
        if (item.object.matrixWorld.elements.some((value, j) => Math.abs(value - reference[j]!) > 1e-10)) {
          throw new Error(`Unclassified setup/motion part: ${item.path}`)
        }
      }
    }
  }
  machine.update(input)
  const groups = Object.fromEntries(groupNames.map(name => [name, [] as string[]]))
  const materials = new Map<string, THREE.MeshBasicMaterial>()
  for (const item of drawables) {
    groups[item.group]!.push(item.path)
    const replace = (source: THREE.Material) => {
      const key = `${source.uuid}:${item.group}`
      let material = materials.get(key)
      if (!material) {
        material = idMaterial(source, groupIds[item.group]!)
        materials.set(key, material)
      }
      return material
    }
    item.idMaterial = Array.isArray(item.nativeMaterial)
      ? item.nativeMaterial.map(replace) : replace(item.nativeMaterial)
    item.object.material = item.idMaterial
  }
  const recordBounds = (box: THREE.Box3): FitBounds => ({
    min: [box.min.x, box.min.y, box.min.z], max: [box.max.x, box.max.y, box.max.z],
  })
  const groupBoundsMetres: Record<string, FitBounds> = {}
  for (const name of groupNames) {
    const box = new THREE.Box3()
    for (const item of drawables) if (item.group === name) box.expandByObject(item.object)
    groupBoundsMetres[name] = recordBounds(box)
  }
  const gl = renderer.getContext()
  const extension = gl.getExtension('WEBGL_debug_renderer_info')
  const ready: FitReady = {
    partPaths: drawables.map(item => item.path), groups, groupIds, channelMapping,
    boundsMetres: recordBounds(new THREE.Box3().setFromObject(scene)), groupBoundsMetres,
    timings,
    renderer: {
      renderer: String(gl.getParameter(extension ? extension.UNMASKED_RENDERER_WEBGL : gl.RENDERER)),
      vendor: String(gl.getParameter(extension ? extension.UNMASKED_VENDOR_WEBGL : gl.VENDOR)),
      version: String(gl.getParameter(gl.VERSION)),
    },
  }
  status.textContent = `Ready: ${ready.partPaths.length} native drawables; render on demand.`
  return ready
})()
loaded.catch(error => { status.textContent = `Fit renderer unavailable: ${String(error)}` })

function base64(bytes: Uint8Array): string {
  // Chromium's native encoder avoids large temporary strings and byte spreads.
  return (bytes as Uint8Array & { toBase64(): string }).toBase64()
}

function sameInput(source: SerializedMechanismInput): boolean {
  if (!inputSolved || source.crankTurns !== input.crankTurns || source.gearing !== input.gearing || source.magnification !== input.magnification) return false
  for (let j = 0; j < CHANNELS; j++) {
    if (source.amplitudes[j] !== input.amplitudes[j] || source.phases[j] !== input.phases[j]) return false
  }
  return setupKeys.every(key => source.setup[key] === input.setup[key])
}

async function render(request: FitRequest): Promise<FitRender> {
  await loaded
  const { width, height } = request
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1) throw new RangeError('Render size must be positive integers')
  if (width > renderer.capabilities.maxTextureSize || height > renderer.capabilities.maxTextureSize) throw new RangeError('Render size exceeds GPU texture capacity')
  if (request.presentation !== 'native' && request.presentation !== 'horizontal-mirror') throw new Error('Unknown presentation')
  if (request.outputs?.some(output => output !== 'rgb' && output !== 'worldPositions')) throw new Error('Unknown appearance output')
  if (request.input.amplitudes.length !== CHANNELS || request.input.phases.length !== CHANNELS) throw new RangeError('Exactly twenty amplitudes and phases required')
  const solveStart = performance.now()
  if (!sameInput(request.input)) {
    inputSolved = false
    input.crankTurns = request.input.crankTurns
    input.amplitudes.set(request.input.amplitudes)
    input.phases.set(request.input.phases)
    input.gearing = request.input.gearing
    input.magnification = request.input.magnification
    Object.assign(input.setup, request.input.setup)
    // Core scene articulation invokes solveMechanism, never a second solver.
    machine.update(input)
    inputSolved = true
  }
  timings.solveMs += performance.now() - solveStart
  const selected = request.groups ? new Set(request.groups) : null
  if (selected) for (const group of selected) if (!(group in groupIds)) throw new Error(`Unknown render group ${group}`)
  for (const item of drawables) item.object.layers.set(!selected || selected.has(item.group) ? 0 : 1)
  camera.position.fromArray(request.camera.positionMetres)
  camera.quaternion.fromArray(request.camera.quaternion).normalize()
  camera.fov = request.camera.verticalFovDegrees
  camera.aspect = width / height
  const principal = request.camera.principalPointViewportPixels
  if (principal) camera.setViewOffset(width, height, width / 2 - principal[0], height / 2 - principal[1], width, height)
  else camera.clearViewOffset()
  camera.updateProjectionMatrix()
  camera.updateMatrixWorld(true)
  if (target.width !== width || target.height !== height) {
    target.setSize(width, height)
    rgba = new Uint8Array(width * height * 4)
    encoded = new Uint8Array(width * height * bytesPerId)
  }
  renderer.setRenderTarget(target)
  const drawStart = performance.now()
  renderer.render(scene, camera)
  timings.drawMs += performance.now() - drawStart
  const readStart = performance.now()
  renderer.readRenderTargetPixels(target, 0, 0, width, height, rgba)
  renderer.setRenderTarget(null)
  timings.readbackMs += performance.now() - readStart
  const encodeStart = performance.now()
  const mirror = request.presentation === 'horizontal-mirror'
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const source = ((height - 1 - y) * width + (mirror ? width - 1 - x : x)) * 4
    const destination = (y * width + x) * bytesPerId
    encoded[destination] = rgba[source]!
    if (bytesPerId === 2) encoded[destination + 1] = rgba[source + 1]!
  }
  const ids = base64(encoded)
  timings.encodeMs += performance.now() - encodeStart
  timings.renders++
  const result: FitRender = { width, height, ids, dtype: bytesPerId === 1 ? 'uint8' : 'uint16' }
  if (request.outputs?.length) renderAppearance(request, result)
  return result
}

window.harmonicFit = {
  ready: () => loaded,
  render,
  async renderBatch(requests) {
    await loaded
    const started = performance.now()
    const results: FitRender[] = []
    for (const request of requests) results.push(await render(request))
    timings.batchMs += performance.now() - started
    return results
  },
}
