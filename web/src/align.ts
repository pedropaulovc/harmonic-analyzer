import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TrackballControls } from 'three/examples/jsm/controls/TrackballControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { loadMachine, type CameraRecord, type Machine, type Presentation } from './scene'
import { applySegmentInput, frameIntervalAt, loadSyncTrack, serializeSyncInput, type SegmentInit, type SyncCameraKey, type SyncTrack } from './sync-track'
import './style.css'
import './align.css'

interface CensusView { viewId: string; rectSourcePixels: [number, number, number, number]; presentation: Presentation }
interface CensusShot { id: string; start: number; end: number; startFrame: number; endFrame: number; classification: string; views: CensusView[] }
interface Census { videoId: string; fps: [number, number]; shots: CensusShot[] }
interface SetupSegment { id: string; start: number; end: number; init: SegmentInit }
type CameraProvenance = 'proposal-accepted' | 'manual'
interface CameraProposal {
  shotId: string
  viewId: string
  frame: number
  camera: CameraRecord
  iou: number | null
  s2rPx: number | null
  r2sPx: number | null
  pnpInliers: number | null
  pnpInlierFraction: number | null
}
interface ReviewEntry { shot: CensusShot; view: CensusView; frame: number; proposal?: CameraProposal }
interface ManualData {
  cameraKeys: (SyncCameraKey & { shotId: string; viewId: string; provenance?: CameraProvenance })[]
  segments: SetupSegment[]
  crank: { t: number; turns: number }[]
}
function element<T extends HTMLElement>(id: string): T {
  const value = document.getElementById(id)
  if (!value) throw new Error(`Missing align control ${id}`)
  return value as T
}
const original = element<HTMLVideoElement>('original')
const overlay = element<HTMLCanvasElement>('overlay')
const status = element('align-status')
const shotSelect = element<HTMLSelectElement>('shot')
const viewSelect = element<HTMLSelectElement>('view')
const segmentSelect = element<HTMLSelectElement>('segment')
const videoSelect = element<HTMLSelectElement>('video-id')
const timeControl = element<HTMLInputElement>('time')
const scrub = element<HTMLInputElement>('scrub')
const fov = element<HTMLInputElement>('fov')
const ppX = element<HTMLInputElement>('pp-x')
const ppY = element<HTMLInputElement>('pp-y')
const azimuth = element<HTMLInputElement>('camera-azimuth')
const elevation = element<HTMLInputElement>('camera-elevation')
const roll = element<HTMLInputElement>('camera-roll')
const distance = element<HTMLInputElement>('camera-distance')
const rotateMode = element<HTMLSelectElement>('rotate-mode')
const crankControl = element<HTMLInputElement>('align-crank')
const gearing = element<HTMLSelectElement>('align-gearing')
const magnification = element<HTMLInputElement>('align-magnification')
const segmentId = element<HTMLInputElement>('segment-id')
const segmentStart = element<HTMLInputElement>('segment-start')
const segmentEnd = element<HTMLInputElement>('segment-end')
const reviewToggle = element<HTMLButtonElement>('review-mode')
const reviewPanel = element('camera-review')
const reviewList = element<HTMLOListElement>('review-list')
const reviewPrevious = element<HTMLButtonElement>('review-previous')
const reviewNext = element<HTMLButtonElement>('review-next')
const reviewAccept = element<HTMLButtonElement>('review-accept')
const input = createMechanismInput()
const renderer = new THREE.WebGLRenderer({ canvas: overlay, antialias: true, alpha: true })
renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
renderer.outputColorSpace = THREE.SRGBColorSpace
renderer.setClearColor(0, 0)
const scene = new THREE.Scene()
scene.add(new THREE.HemisphereLight(0xffffff, 0x404050, 1.6))
const light = new THREE.DirectionalLight(0xffffff, 2.2)
light.position.set(2, 3, 2)
scene.add(light)
const environment = new RoomEnvironment()
const pmrem = new THREE.PMREMGenerator(renderer)
const environmentTarget = pmrem.fromScene(environment)
scene.environment = environmentTarget.texture
pmrem.dispose()
environment.dispose()
const camera = new THREE.PerspectiveCamera(35, 16 / 9, 0.005, 100)
camera.position.set(1.2, 1, 1.6)
camera.lookAt(0, 0, 0)
camera.layers.enable(1)
const controlCamera = new THREE.PerspectiveCamera()
const pivot = new THREE.Vector3()
const orientationOffset = new THREE.Quaternion()
const worldUp = new THREE.Vector3(0, 1, 0)
const principalPoint = new THREE.Vector2(960, 540)
const raycaster = new THREE.Raycaster()
const rayPoint = new THREE.Vector2()
const intersections: THREE.Intersection[] = []
const modelRoots: THREE.Object3D[] = []
const modelBounds = new THREE.Box3()
const rollAxis = new THREE.Vector3(0, 0, 1)
const offset = new THREE.Vector3()
const spherical = new THREE.Spherical()
const forward = new THREE.Vector3()
const lookMatrix = new THREE.Matrix4()
const referenceRotation = new THREE.Quaternion()
const rollRotation = new THREE.Quaternion()
const pivotMarker = new THREE.Mesh(new THREE.SphereGeometry(1, 12, 8), new THREE.MeshBasicMaterial({ color: 0xffcb5b, depthTest: false, depthWrite: false }))
pivotMarker.layers.set(1)
pivotMarker.renderOrder = 1000
pivotMarker.visible = false
scene.add(pivotMarker)
let controls: OrbitControls | TrackballControls
let controlsNeedUpdate = false
let pivotSource: 'centre' | 'bounds' | 'picked' = 'bounds'
let pivotRevision = 0
let rotationMode: 'turntable' | 'free' = 'turntable'
try { if (localStorage.getItem('harmonic-align-rotation-mode') === 'free') rotationMode = 'free' } catch { /* Storage may be disabled. */ }
rotateMode.value = rotationMode
let machine: Machine | null = null
let census: Census | null = null
let segments: SetupSegment[] = []
let manual: ManualData = { cameraKeys: [], segments: [], crank: [] }
let track: SyncTrack | null = null
let currentShot: CensusShot | undefined
let currentView: CensusView | undefined
let currentSegment: SetupSegment | undefined
let loaded = false
let loadingVersion = 0
let reviewMode = false
let reviewBusy = false
let reviewIndex = 0
let reviewQueue: ReviewEntry[] = []
let reviewItems: HTMLButtonElement[] = []
let reviewedCount = 0
let reviewSeedCamera: CameraRecord | null = null
let reviewSeedSource: string | null = null
const setupControls: { key: keyof MechanismInput['setup']; control: HTMLInputElement }[] = []
const channelControls: { amplitude: HTMLInputElement; phase: HTMLInputElement }[] = []

let renderFrame = 0
function render(): void {
  if (renderFrame) return
  renderFrame = requestAnimationFrame(() => {
    if (controlsNeedUpdate && controls instanceof TrackballControls) {
      controlsNeedUpdate = false
      controls.update()
    }
    renderFrame = 0
    if (!machine || !currentView) return
    try {
      machine.update(input)
      updateProjection()
      syncControlMatrices()
      pivotMarker.position.copy(pivot)
      pivotMarker.scale.setScalar(Math.max(0.0001, camera.position.distanceTo(pivot) * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * 0.012))
      pivotMarker.visible = modelRoots.length > 0
      const width = Math.max(1, Math.round(overlay.clientWidth)), height = Math.max(1, Math.round(overlay.clientHeight))
      renderer.setSize(width, height, false)
      renderer.render(scene, camera)
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : String(error)
      status.dataset.state = 'error'
    }
  })
}

function updateProjection(): void {
  const rect = currentView?.rectSourcePixels ?? [0, 0, 1920, 1080]
  camera.aspect = rect[2]! / rect[3]!
  camera.setViewOffset(rect[2]!, rect[3]!, rect[2]! / 2 - principalPoint.x, rect[3]! / 2 - principalPoint.y, rect[2]!, rect[3]!)
  camera.updateProjectionMatrix()
  camera.updateMatrixWorld(true)
}

function syncControlMatrices(): void {
  camera.updateMatrixWorld(true)
  // Orbit a look-at proxy, but pan and cursor-zoom in the actual camera's
  // screen space. The orientation offset keeps an off-centre pivot from
  // snapping the authored camera direction or removing its roll.
  controlCamera.matrix.copy(camera.matrix)
  controlCamera.matrixWorld.copy(camera.matrixWorld)
  controlCamera.matrixWorldInverse.copy(camera.matrixWorldInverse)
  controlCamera.projectionMatrix.copy(camera.projectionMatrix)
  controlCamera.projectionMatrixInverse.copy(camera.projectionMatrixInverse)
  controlCamera.fov = camera.fov
  controlCamera.aspect = camera.aspect
}

function cameraRoll(): number {
  forward.set(0, 0, -1).applyQuaternion(camera.quaternion)
  offset.copy(camera.position).add(forward)
  lookMatrix.lookAt(camera.position, offset, worldUp)
  referenceRotation.setFromRotationMatrix(lookMatrix).invert().multiply(camera.quaternion)
  const degrees = THREE.MathUtils.radToDeg(2 * Math.atan2(referenceRotation.z, referenceRotation.w))
  return THREE.MathUtils.euclideanModulo(degrees + 180, 360) - 180
}

function syncCameraSliders(): void {
  offset.subVectors(camera.position, pivot)
  spherical.setFromVector3(offset)
  const metres = Math.max(spherical.radius, 0.00001)
  const logDistance = Math.log10(metres)
  distance.min = String(Math.min(-2, logDistance))
  distance.max = String(Math.max(Math.log10(20), logDistance))
  const rect = currentView?.rectSourcePixels ?? [0, 0, 1920, 1080]
  ppX.max = String(rect[2])
  ppY.max = String(rect[3])
  for (const [control, value, label] of [
    [azimuth, THREE.MathUtils.radToDeg(spherical.theta), '°'],
    [elevation, 90 - THREE.MathUtils.radToDeg(spherical.phi), '°'],
    [roll, cameraRoll(), '°'],
    [distance, logDistance, ''],
    [fov, camera.fov, '°'],
    [ppX, principalPoint.x, ' px'],
    [ppY, principalPoint.y, ' px'],
  ] as const) {
    control.value = String(value)
    element<HTMLOutputElement>(`${control.id}-value`).value = control === distance ? `${metres.toFixed(3)} m` : `${value.toFixed(2)}${label}`
  }
}

function visibleModelPoint(x: number, y: number): THREE.Vector3 | null {
  updateProjection()
  scene.updateMatrixWorld(true)
  rayPoint.set(currentView?.presentation === 'horizontal-mirror' ? -x : x, y)
  raycaster.setFromCamera(rayPoint, camera)
  intersections.length = 0
  raycaster.intersectObjects(modelRoots, true, intersections)
  for (const hit of intersections) {
    if (!(hit.object instanceof THREE.Mesh)) continue
    let node: THREE.Object3D | null = hit.object
    while (node?.visible) node = node.parent
    if (!node) return hit.point
  }
  return null
}

function defaultPivot(): void {
  if (machine?.availability === 'available') machine.update(input)
  const hit = visibleModelPoint(0, 0)
  if (hit) {
    pivot.copy(hit)
    pivotSource = 'centre'
  } else {
    modelBounds.makeEmpty()
    for (const root of modelRoots) modelBounds.expandByObject(root)
    if (!modelBounds.isEmpty()) modelBounds.getCenter(pivot)
    else pivot.set(0, 0, 0)
    pivotSource = 'bounds'
  }
  pivotRevision++
}

function controlSpeeds(fine: boolean): void {
  const factor = fine ? 0.25 : 1
  controls.rotateSpeed = 0.4 * factor
  controls.panSpeed = (controls instanceof OrbitControls ? 1 : 0.3) * factor
  controls.zoomSpeed = (controls instanceof OrbitControls ? 1 : 1.2) * factor
}

function rebaseControls(): void {
  controls?.dispose()
  controlCamera.copy(camera)
  controlCamera.up.copy(rotationMode === 'turntable' ? worldUp : camera.up)
  controlCamera.lookAt(pivot)
  if (rotationMode === 'turntable') {
    controls = new OrbitControls(controlCamera, overlay)
    controls.enableDamping = false
    controls.zoomToCursor = true
    controls.screenSpacePanning = true
  } else {
    controls = new TrackballControls(controlCamera, overlay)
    controls.staticMoving = true
    // A/S are review shortcuts, not Trackball's default mouse-mode keys.
    controls.keys = ['', '', '']
  }
  controls.target.copy(pivot)
  controls.minDistance = 0.001
  controls.update()
  orientationOffset.copy(controlCamera.quaternion).invert().multiply(camera.quaternion)
  syncControlMatrices()
  controls.addEventListener('change', () => {
    camera.position.copy(controlCamera.position)
    camera.quaternion.copy(controlCamera.quaternion).multiply(orientationOffset)
    camera.up.copy(worldUp).applyQuaternion(camera.quaternion)
    pivot.copy(controls.target)
    updateProjection()
    syncControlMatrices()
    syncCameraSliders()
    render()
  })
  controlsNeedUpdate = false
  controlSpeeds(false)
  syncCameraSliders()
}

function applyCamera(record: CameraRecord): void {
  camera.position.fromArray(record.positionMetres)
  camera.quaternion.fromArray(record.quaternion)
  camera.up.copy(worldUp).applyQuaternion(camera.quaternion)
  camera.fov = record.verticalFovDegrees
  principalPoint.set(record.principalPointViewportPixels?.[0] ?? (currentView?.rectSourcePixels[2] ?? 1920) / 2, record.principalPointViewportPixels?.[1] ?? (currentView?.rectSourcePixels[3] ?? 1080) / 2)
  updateProjection()
  defaultPivot()
  rebaseControls()
}

function cameraRecord(): CameraRecord {
  return { positionMetres: camera.position.toArray() as [number, number, number], quaternion: camera.quaternion.toArray() as [number, number, number, number], verticalFovDegrees: camera.fov, principalPointViewportPixels: principalPoint.toArray() as [number, number] }
}

function reloadCamera(): void {
  if (!currentShot || !currentView) return
  if (census) {
    const fps = census.fps[0] / census.fps[1]
    const frame = Math.round(original.currentTime * fps)
    const exact = manual.cameraKeys.find(key => key.shotId === currentShot!.id && key.viewId === currentView!.viewId && Math.round(key.t * fps) === frame)
    if (exact) { applyCamera(exact.camera); render(); return }
  }
  const fitted = track?.data.shots.find(shot => shot.id === currentShot!.id)?.views.find(view => view.viewId === currentView!.viewId)?.cameraKeys ?? []
  const keys = [...fitted]
  for (const key of manual.cameraKeys) {
    if (key.shotId !== currentShot.id || key.viewId !== currentView.viewId) continue
    const index = keys.findIndex(existing => existing.t === key.t)
    if (index < 0) keys.push(key)
    else keys[index] = key
  }
  keys.sort((a, b) => a.t - b.t)
  if (keys.length) {
    let index = 0
    while (index + 1 < keys.length && keys[index + 1]!.t <= original.currentTime) index++
    const a = keys[index]!, b = keys[index + 1] ?? a
    const f = b.t > a.t ? Math.max(0, Math.min(1, (original.currentTime - a.t) / (b.t - a.t))) : 0
    const position = new THREE.Vector3().fromArray(a.camera.positionMetres).lerp(new THREE.Vector3().fromArray(b.camera.positionMetres), f)
    const quaternion = new THREE.Quaternion().fromArray(a.camera.quaternion).normalize().slerp(new THREE.Quaternion().fromArray(b.camera.quaternion).normalize(), f)
    const rect = currentView.rectSourcePixels
    const p0 = a.camera.principalPointViewportPixels ?? [rect[2] / 2, rect[3] / 2]
    const p1 = b.camera.principalPointViewportPixels ?? [rect[2] / 2, rect[3] / 2]
    applyCamera({ positionMetres: position.toArray() as [number, number, number], quaternion: quaternion.toArray() as [number, number, number, number], verticalFovDegrees: a.camera.verticalFovDegrees + (b.camera.verticalFovDegrees - a.camera.verticalFovDegrees) * f, principalPointViewportPixels: [p0[0]! + (p1[0]! - p0[0]!) * f, p0[1]! + (p1[1]! - p0[1]!) * f] })
  } else {
    camera.position.set(1.2, 1, 1.6)
    camera.up.copy(worldUp)
    modelBounds.makeEmpty()
    for (const root of modelRoots) modelBounds.expandByObject(root)
    modelBounds.isEmpty() ? offset.set(0, 0, 0) : modelBounds.getCenter(offset)
    camera.lookAt(offset)
    applyCamera({ positionMetres: camera.position.toArray() as [number, number, number], quaternion: camera.quaternion.toArray() as [number, number, number, number], verticalFovDegrees: 35 })
  }
  render()
}

function selectView(): void {
  currentView = currentShot?.views.find(view => view.viewId === viewSelect.value)
  overlay.hidden = !currentView
  element<HTMLButtonElement>('save-camera').disabled = !currentView || reviewBusy
  if (!currentView) return
  const [x, y, w, h] = currentView.rectSourcePixels
  overlay.style.left = `${x / 1920 * 100}%`
  overlay.style.top = `${y / 1080 * 100}%`
  overlay.style.width = `${w / 1920 * 100}%`
  overlay.style.height = `${h / 1080 * 100}%`
  overlay.style.transform = currentView.presentation === 'horizontal-mirror' ? 'scaleX(-1)' : ''
  reloadCamera()
}

function refreshInputControls(): void {
  crankControl.value = String(input.crankTurns)
  gearing.value = input.gearing
  magnification.value = String(input.magnification)
  for (const { key, control } of setupControls) control.value = input.setup[key] === null ? '' : String(input.setup[key])
  for (let index = 0; index < channelControls.length; index++) {
    channelControls[index]!.amplitude.value = String(input.amplitudes[index])
    channelControls[index]!.phase.value = String(input.phases[index])
  }
}

function selectSegment(segment: SetupSegment | undefined): void {
  currentSegment = segment
  const defaults = createMechanismInput()
  input.amplitudes.set(defaults.amplitudes)
  input.phases.set(defaults.phases)
  input.gearing = defaults.gearing
  input.magnification = defaults.magnification
  Object.assign(input.setup, defaults.setup)
  if (segment) {
    // Carry partially specified setups forward, then let the fitted/full input
    // and the owner's manual entry override the selected segment.
    for (const previous of segments) {
      if (previous.start > segment.start) break
      applySegmentInput(input, previous.init)
    }
    const fitted = track?.data.segments.find(item => item.id === segment.id)
    if (fitted) applySegmentInput(input, fitted.input)
    const override = manual.segments.find(item => item.id === segment.id)
    if (override) applySegmentInput(input, override.init)
    segmentSelect.value = segment.id
    segmentId.value = segment.id
    segmentStart.value = String(segment.start)
    segmentEnd.value = String(segment.end)
  }
  refreshInputControls()
}

function updateTime(): void {
  if (!loaded || !census) return
  const t = original.currentTime
  const fps = census.fps[0] / census.fps[1]
  const frame = Math.round(t * fps)
  timeControl.value = t.toFixed(6)
  scrub.value = String(t)
  const shot = frameIntervalAt(census.shots, frame)
  if (shot !== currentShot) {
    currentShot = shot
    shotSelect.value = shot?.id ?? ''
    viewSelect.replaceChildren(...(shot?.views ?? []).map(view => new Option(view.viewId, view.viewId)))
    selectView()
  }
  const segment = segments.find(item => frame >= Math.round(item.start * fps) && frame < Math.round(item.end * fps))
  if (segment !== currentSegment) selectSegment(segment)
  const keys = [...(track?.data.crank ?? [])].map(key => ({ t: key.t, turns: key.turns }))
  for (const key of manual.crank) {
    const index = keys.findIndex(item => item.t === key.t)
    if (index < 0) keys.push(key)
    else keys[index] = key
  }
  keys.sort((a, b) => a.t - b.t)
  if (keys.length) {
    let index = 0
    while (index + 1 < keys.length && keys[index + 1]!.t <= t) index++
    const a = keys[index]!, b = keys[index + 1]
    const f = b ? Math.max(0, Math.min(1, (t - a.t) / (b.t - a.t))) : 0
    input.crankTurns = b ? a.turns + (b.turns - a.turns) * f : a.turns
  }
  crankControl.value = String(input.crankTurns)
  status.textContent = `${shot?.id ?? 'No shot'} · ${t.toFixed(3)} s · frame ${frame}`
  status.dataset.state = 'ready'
  render()
}

async function seek(t: number): Promise<void> {
  if (!Number.isFinite(t)) throw new Error('Seek time must be finite')
  original.pause()
  t = Math.max(0, Math.min(original.duration || 0, t))
  // Browsers quantize media times; the current source frame needs no seeked event.
  const fps = census ? census.fps[0] / census.fps[1] : undefined
  if (fps ? Math.round(original.currentTime * fps) !== Math.round(t * fps) : original.currentTime !== t) {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => { cleanup(); reject(new Error('Video seek timed out')) }, 15000)
      const done = () => { cleanup(); resolve() }
      const cleanup = () => { clearTimeout(timer); original.removeEventListener('seeked', done) }
      original.addEventListener('seeked', done)
      original.currentTime = t
    })
  }
  updateTime()
}

function refreshReviewQueue(): void {
  reviewedCount = 0
  for (let index = 0; index < reviewQueue.length; index++) {
    const entry = reviewQueue[index]!, button = reviewItems[index]!
    const hasCamera = manual.cameraKeys.some(key => key.shotId === entry.shot.id && key.viewId === entry.view.viewId)
    if (hasCamera) reviewedCount++
    button.dataset.reviewed = String(hasCamera)
    button.lastElementChild!.textContent = hasCamera ? 'Manual camera' : 'Not saved'
    button.setAttribute('aria-current', String(index === reviewIndex))
    button.disabled = reviewBusy
  }
  element('review-count').textContent = `${reviewedCount} of ${reviewQueue.length} reviewed`
  reviewToggle.disabled = !loaded || reviewBusy
  reviewToggle.setAttribute('aria-pressed', String(reviewMode))
  reviewPanel.hidden = !reviewMode
  reviewPrevious.disabled = reviewBusy || reviewIndex === 0
  reviewNext.disabled = reviewBusy || reviewIndex + 1 >= reviewQueue.length
  reviewAccept.disabled = reviewBusy || !reviewSeedCamera
  element<HTMLButtonElement>('save-camera').disabled = !currentView || reviewBusy
  shotSelect.disabled = reviewMode
  viewSelect.disabled = reviewMode
}

function buildReviewQueue(proposals: CameraProposal[]): void {
  reviewQueue = []
  for (const shot of census?.shots ?? []) {
    if (shot.classification !== 'machine' && shot.classification !== 'transition') continue
    for (const view of shot.views) {
      const proposal = proposals.find(item => item.shotId === shot.id && item.viewId === view.viewId)
      reviewQueue.push({ shot, view, proposal, frame: proposal?.frame ?? Math.floor((shot.startFrame + shot.endFrame - 1) / 2) })
    }
  }
  reviewQueue.sort((a, b) => a.frame - b.frame)
  reviewIndex = 0
  reviewSeedCamera = null
  reviewSeedSource = null
  reviewItems = reviewQueue.map((entry, index) => {
    const item = document.createElement('li')
    const button = document.createElement('button')
    const label = document.createElement('span'), saved = document.createElement('span')
    label.textContent = `${entry.shot.id} · ${entry.view.viewId}`
    button.title = label.textContent
    button.append(label, saved)
    button.addEventListener('click', () => { void showReviewEntry(index).catch(handleError) })
    item.append(button)
    reviewList.append(item)
    return button
  })
  refreshReviewQueue()
}

async function showReviewEntry(index: number): Promise<void> {
  if (!reviewMode || reviewBusy || !census) return
  const entry = reviewQueue[index]
  if (!entry) return
  const version = loadingVersion
  reviewBusy = true
  reviewIndex = index
  refreshReviewQueue()
  try {
    await seek(entry.frame * census.fps[1] / census.fps[0])
    if (version !== loadingVersion || !reviewMode) return
    viewSelect.value = entry.view.viewId
    selectView()
    const fps = census.fps[0] / census.fps[1]
    let previous: ManualData['cameraKeys'][number] | undefined
    let nearest: ManualData['cameraKeys'][number] | undefined
    for (const key of manual.cameraKeys) {
      const frame = Math.round(key.t * fps)
      if (frame <= entry.frame && (!previous || key.t > previous.t)) previous = key
      if (!nearest || Math.abs(frame - entry.frame) < Math.abs(Math.round(nearest.t * fps) - entry.frame)) nearest = key
    }
    const accepted = previous ?? nearest
    reviewSeedCamera = entry.proposal?.camera ?? accepted?.camera ?? null
    reviewSeedSource = entry.proposal ? 'proposal' : accepted ? `accepted camera from ${accepted.shotId}` : null
    if (reviewSeedCamera) { applyCamera(reviewSeedCamera); render() }
    element('review-source').textContent = `View ${index + 1} of ${reviewQueue.length} · frame ${entry.frame} · ${reviewSeedSource ?? 'no proposal or accepted camera; adjust and save with C'}`
  } finally {
    if (version === loadingVersion) {
      reviewBusy = false
      refreshReviewQueue()
    }
  }
}

async function toggleReviewQueue(): Promise<void> {
  if (!loaded || reviewBusy) return
  if (reviewMode) {
    reviewMode = false
    refreshReviewQueue()
    return
  }
  const version = loadingVersion
  reviewBusy = true
  refreshReviewQueue()
  try {
    const response = await fetch(`/__sync/proposals/${videoSelect.value}`)
    if (!response.ok) throw new Error('Camera proposals unavailable')
    const data = await response.json() as { cameras: CameraProposal[] }
    if (version !== loadingVersion) return
    reviewList.replaceChildren()
    reviewMode = true
    buildReviewQueue(data.cameras)
  } finally {
    if (version === loadingVersion) {
      reviewBusy = false
      refreshReviewQueue()
    }
  }
  await showReviewEntry(0)
}

async function saveReviewCamera(provenance: CameraProvenance, advance = provenance === 'proposal-accepted'): Promise<void> {
  if (reviewBusy || !census) return
  const entry = reviewQueue[reviewIndex]
  if (!entry) return
  if (provenance === 'proposal-accepted' && !reviewSeedCamera) throw new Error('No proposed camera to accept; adjust and save with C')
  if (provenance === 'manual' && (currentShot?.id !== entry.shot.id || currentView?.viewId !== entry.view.viewId)) throw new Error('Return to this review view with N/P or the list before saving')
  const version = loadingVersion
  reviewBusy = true
  refreshReviewQueue()
  try {
    if (provenance === 'proposal-accepted') {
      await seek(entry.frame * census.fps[1] / census.fps[0])
      if (version !== loadingVersion) return
      viewSelect.value = entry.view.viewId
      selectView()
      applyCamera(reviewSeedCamera!)
      render()
    }
    await save('camera', provenance)
  } finally {
    if (version === loadingVersion) {
      reviewBusy = false
      refreshReviewQueue()
    }
  }
  if (advance && version === loadingVersion) {
    for (let offset = 1; offset <= reviewQueue.length; offset++) {
      const index = (reviewIndex + offset) % reviewQueue.length
      const next = reviewQueue[index]!
      if (!manual.cameraKeys.some(key => key.shotId === next.shot.id && key.viewId === next.view.viewId)) {
        await showReviewEntry(index)
        break
      }
    }
  }
}

async function save(kind: 'camera' | 'segment' | 'crank', provenance: CameraProvenance = 'manual'): Promise<void> {
  const id = videoSelect.value, version = loadingVersion
  const body: Record<string, unknown> = { videoId: id }
  if (kind === 'camera') {
    if (!currentShot || !currentView) throw new Error('Select a machine shot/view before saving')
    const frame = provenance === 'proposal-accepted' ? reviewQueue[reviewIndex]?.frame : census ? Math.round(original.currentTime * census.fps[0] / census.fps[1]) : undefined
    const t = reviewMode && census && frame !== undefined ? frame * census.fps[1] / census.fps[0] : original.currentTime
    body.cameraKey = { shotId: currentShot.id, viewId: currentView.viewId, t, camera: cameraRecord(), provenance }
  } else if (kind === 'segment') {
    const { crankTurns: _crank, ...init } = serializeSyncInput(input)
    body.segment = { id: segmentId.value.trim(), start: Number(segmentStart.value), end: Number(segmentEnd.value), init }
  } else body.crank = { t: original.currentTime, turns: input.crankTurns }
  status.textContent = 'Saving…'
  status.dataset.state = 'loading'
  const response = await fetch('/__sync/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!response.ok) throw new Error(await response.text())
  const saved = await fetch(`/__sync/manual/${id}`)
  if (!saved.ok) throw new Error('Could not reload manual entries')
  const nextManual = await saved.json() as ManualData
  if (version !== loadingVersion) return
  manual = nextManual
  refreshReviewQueue()
  if (kind === 'segment') {
    const entry = manual.segments.find(item => item.id === segmentId.value.trim())!
    const index = segments.findIndex(item => item.id === entry.id)
    if (index < 0) { segments.push(entry); segmentSelect.add(new Option(entry.id, entry.id)) }
    else segments[index] = entry
    segments.sort((a, b) => a.start - b.start)
    currentSegment = entry
  }
  status.textContent = `Saved ${kind} at ${original.currentTime.toFixed(3)} s`
  status.dataset.state = 'saved'
}

function handleError(error: unknown): void {
  status.textContent = error instanceof Error ? error.message : String(error)
  status.dataset.state = 'error'
}

async function loadVideo(): Promise<void> {
  const version = ++loadingVersion
  loaded = false
  reviewBusy = false
  currentShot = undefined
  currentView = undefined
  currentSegment = undefined
  reviewQueue = []
  reviewItems = []
  reviewList.replaceChildren()
  reviewSeedCamera = null
  refreshReviewQueue()
  const id = videoSelect.value
  const base = `${import.meta.env.BASE_URL}sync/videos/${id}`
  status.textContent = 'Loading original video and shot census…'
  status.dataset.state = 'loading'
  original.src = `/__sync/video/${id}.mp4`
  const metadata = new Promise<void>((resolve, reject) => {
    original.addEventListener('loadeddata', () => resolve(), { once: true })
    original.addEventListener('error', () => reject(new Error('Original video unavailable. Put the MP4 in ~/data/harmonic-analyzer-videos and use the Vite dev server.')), { once: true })
  })
  original.load()
  const [shotResponse, segmentResponse, manualResponse, runtime] = await Promise.all([
    fetch(`${base}/shots.json`), fetch(`${base}/segments.json`), fetch(`/__sync/manual/${id}`), loadSyncTrack(id),
  ])
  if (!shotResponse.ok || !manualResponse.ok) throw new Error('Shot census or manual endpoint unavailable')
  const hasSegments = segmentResponse.ok && segmentResponse.headers.get('content-type')?.includes('application/json')
  const [nextCensus, nextSegments, nextManual] = await Promise.all([
    shotResponse.json() as Promise<Census>,
    hasSegments ? segmentResponse.json() as Promise<{ segments: SetupSegment[] }> : Promise.resolve({ segments: [] as SetupSegment[] }),
    manualResponse.json() as Promise<ManualData>,
  ])
  await metadata
  if (version !== loadingVersion) return
  census = nextCensus
  segments = nextSegments.segments.length ? nextSegments.segments.sort((a, b) => a.start - b.start) : [{ id: 'default', start: 0, end: original.duration, init: {} }]
  manual = nextManual
  track = runtime
  for (const entry of manual.segments) {
    const index = segments.findIndex(item => item.id === entry.id)
    if (index < 0) segments.push(entry)
    else segments[index] = { ...segments[index]!, ...entry, init: { ...segments[index]!.init, ...entry.init, setup: { ...segments[index]!.init.setup, ...entry.init.setup } } }
  }
  segments.sort((a, b) => a.start - b.start)
  shotSelect.replaceChildren(...census.shots.map(shot => new Option(`${shot.start.toFixed(2)}–${shot.end.toFixed(2)} · ${shot.id}`, shot.id)))
  segmentSelect.replaceChildren(...segments.map(segment => new Option(segment.id, segment.id)))
  scrub.max = String(original.duration)
  timeControl.max = String(original.duration)
  element<HTMLAnchorElement>('companion-link').href = `./?video=${id}`
  loaded = true
  const firstMachine = census.shots.find(shot => shot.classification === 'machine' && shot.views.length)
  await seek((firstMachine?.startFrame ?? 0) * census.fps[1] / census.fps[0])
  refreshReviewQueue()
  if (reviewMode) {
    reviewMode = false
    await toggleReviewQueue()
  }
}

// Physical setup coordinates remain in SI units; phase controls are radians.
for (const key of Object.keys(input.setup) as (keyof MechanismInput['setup'])[]) {
  const label = document.createElement('label')
  label.textContent = key
  const control = document.createElement('input')
  control.type = 'number'
  control.step = '0.001'
  control.id = `setup-${key}`
  if (key === 'counterHeightM') control.placeholder = 'auto level (blank)'
  label.append(control)
  element('setup-fields').append(label)
  setupControls.push({ key, control })
  control.addEventListener('input', () => {
    if (key === 'counterHeightM' && control.value === '') input.setup.counterHeightM = null
    else input.setup[key] = Number(control.value)
    render()
  })
}
for (let index = 0; index < 20; index++) {
  const row = document.createElement('div')
  row.className = 'align-channel'
  const name = document.createElement('span')
  name.textContent = `H${MECHANISM_DATA.harmonicNumbers[index]}`
  row.append(name)
  const fields: HTMLInputElement[] = []
  for (const kind of ['amplitude', 'phase'] as const) {
    const label = document.createElement('label')
    label.textContent = kind === 'amplitude' ? 'Amplitude' : 'Phase (rad)'
    const control = document.createElement('input')
    control.type = 'number'
    control.step = '0.001'
    control.id = `${kind}-${index}`
    if (kind === 'amplitude') { control.min = '-1'; control.max = '1' }
    control.addEventListener('input', () => { (kind === 'amplitude' ? input.amplitudes : input.phases)[index] = Number(control.value); render() })
    label.append(control)
    row.append(label)
    fields.push(control)
  }
  channelControls.push({ amplitude: fields[0]!, phase: fields[1]! })
  element('align-channels').append(row)
}
refreshInputControls()
for (const [control, fineStep] of [[azimuth, 0.1], [elevation, 0.1], [roll, 0.1], [distance, 0.001], [fov, 0.1], [ppX, 0.1], [ppY, 0.1]] as const) {
  // Loading a saved camera must not snap its values onto an HTML range step.
  control.step = 'any'
  control.addEventListener('keydown', event => {
    const direction = event.key === 'ArrowRight' || event.key === 'ArrowUp' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowDown' ? -1 : 0
    if (!direction) return
    event.preventDefault()
    control.value = String(THREE.MathUtils.clamp(Number(control.value) + direction * fineStep * (event.shiftKey ? 0.25 : 1), Number(control.min), Number(control.max)))
    control.dispatchEvent(new Event('input', { bubbles: true }))
  })
  control.addEventListener('input', () => {
    if (control === fov) camera.fov = Number(fov.value)
    else if (control === ppX) principalPoint.x = Number(ppX.value)
    else if (control === ppY) principalPoint.y = Number(ppY.value)
    else if (control === roll) {
      rollRotation.setFromAxisAngle(rollAxis, THREE.MathUtils.degToRad(Number(roll.value) - cameraRoll()))
      camera.quaternion.multiply(rollRotation)
      camera.up.copy(worldUp).applyQuaternion(camera.quaternion)
      rebaseControls()
    } else {
      spherical.setFromVector3(offset.subVectors(camera.position, pivot))
      if (control === azimuth) spherical.theta = THREE.MathUtils.degToRad(Number(azimuth.value))
      if (control === elevation) spherical.phi = THREE.MathUtils.degToRad(90 - Number(elevation.value))
      if (control === distance) spherical.radius = 10 ** Number(distance.value)
      controlCamera.position.copy(pivot).add(offset.setFromSpherical(spherical))
      controlCamera.lookAt(pivot)
      camera.position.copy(controlCamera.position)
      camera.quaternion.copy(controlCamera.quaternion).multiply(orientationOffset)
      camera.up.copy(worldUp).applyQuaternion(camera.quaternion)
      rebaseControls()
    }
    updateProjection()
    syncControlMatrices()
    syncCameraSliders()
    render()
  })
}
rotateMode.addEventListener('change', () => {
  rotationMode = rotateMode.value === 'free' ? 'free' : 'turntable'
  try { localStorage.setItem('harmonic-align-rotation-mode', rotationMode) } catch { /* Storage may be disabled. */ }
  rebaseControls()
  render()
})
overlay.addEventListener('dblclick', event => {
  const rect = overlay.getBoundingClientRect()
  const hit = visibleModelPoint((event.clientX - rect.left) / rect.width * 2 - 1, 1 - (event.clientY - rect.top) / rect.height * 2)
  if (!hit) return
  pivot.copy(hit)
  pivotSource = 'picked'
  pivotRevision++
  rebaseControls()
  render()
})
overlay.addEventListener('pointerdown', event => {
  controlSpeeds(event.shiftKey)
  if (controls instanceof OrbitControls) {
    const modifier = event.shiftKey || event.ctrlKey || event.metaKey
    const rotate = !event.ctrlKey && !event.metaKey
    // OrbitControls normally treats Shift-left as pan; here Shift is precision.
    controls.mouseButtons.LEFT = modifier ? (rotate ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE) : THREE.MOUSE.ROTATE
    controls.mouseButtons.RIGHT = modifier ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN
  }
}, { capture: true })
for (const eventName of ['pointermove', 'wheel'] as const) overlay.addEventListener(eventName, event => {
  controlSpeeds(event.shiftKey)
  if (controls instanceof TrackballControls) { controlsNeedUpdate = true; render() }
}, { capture: true })
overlay.addEventListener('pointerup', () => {
  if (controls instanceof TrackballControls) { controlsNeedUpdate = true; render() }
}, { capture: true })
rebaseControls()
element<HTMLInputElement>('opacity').addEventListener('input', event => { overlay.style.opacity = (event.target as HTMLInputElement).value })
overlay.style.opacity = '0.5'
gearing.addEventListener('change', () => { input.gearing = gearing.value as MechanismInput['gearing']; render() })
magnification.addEventListener('input', () => { input.magnification = Number(magnification.value); render() })
crankControl.addEventListener('input', () => { input.crankTurns = Number(crankControl.value); render() })
shotSelect.addEventListener('change', () => { const shot = census?.shots.find(item => item.id === shotSelect.value); if (shot && census) void seek(shot.startFrame * census.fps[1] / census.fps[0]).catch(handleError) })
viewSelect.addEventListener('change', selectView)
segmentSelect.addEventListener('change', () => { const segment = segments.find(item => item.id === segmentSelect.value); if (segment && census) void seek(Math.round(segment.start * census.fps[0] / census.fps[1]) * census.fps[1] / census.fps[0]).catch(handleError) })
videoSelect.addEventListener('change', () => { void loadVideo().catch(handleError) })
element('reset-camera').addEventListener('click', reloadCamera)
element('seek').addEventListener('click', () => { void seek(Number(timeControl.value)).catch(handleError) })
timeControl.addEventListener('keydown', event => { if (event.key === 'Enter') void seek(Number(timeControl.value)).catch(handleError) })
scrub.addEventListener('change', () => { void seek(Number(scrub.value)).catch(handleError) })
element('save-camera').addEventListener('click', () => { void (reviewMode ? saveReviewCamera('manual') : save('camera')).catch(handleError) })
for (const [id, kind] of [['save-segment', 'segment'], ['save-crank', 'crank']] as const) element(id).addEventListener('click', () => { void save(kind).catch(handleError) })
reviewToggle.addEventListener('click', () => { void toggleReviewQueue().catch(handleError) })
reviewPrevious.addEventListener('click', () => { void showReviewEntry(reviewIndex - 1).catch(handleError) })
reviewNext.addEventListener('click', () => { void showReviewEntry(reviewIndex + 1).catch(handleError) })
reviewAccept.addEventListener('click', () => { void saveReviewCamera('proposal-accepted').catch(handleError) })
const stepFrame = (delta: number) => {
  if (!census) return
  const fps = census.fps[0] / census.fps[1]
  let frame = Math.round(original.currentTime * fps) + delta
  const entry = reviewMode ? reviewQueue[reviewIndex] : undefined
  if (entry) frame = Math.max(entry.shot.startFrame, Math.min(entry.shot.endFrame - 1, frame))
  void seek(frame / fps).catch(handleError)
}
element('previous-frame').addEventListener('click', () => stepFrame(-1))
element('next-frame').addEventListener('click', () => stepFrame(1))
element('play').addEventListener('click', () => { if (original.paused) void original.play().catch(handleError); else original.pause() })
original.addEventListener('play', () => { element('play').textContent = 'Pause' })
original.addEventListener('pause', () => { element('play').textContent = 'Play' })
original.addEventListener('timeupdate', updateTime)
original.addEventListener('seeked', updateTime)
new ResizeObserver(() => { if (controls instanceof TrackballControls) controls.handleResize(); render() }).observe(element('align-stage'))
document.addEventListener('keydown', event => {
  if ((event.target as HTMLElement).matches('input, select, textarea') || event.ctrlKey || event.altKey || event.metaKey) return
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); stepFrame((event.key === 'ArrowLeft' ? -1 : 1) * (event.shiftKey ? 10 : 1)) }
  else if (event.code === 'Space') { event.preventDefault(); element('play').click() }
  else if (reviewMode && event.key.toLowerCase() === 'a') reviewAccept.click()
  else if (reviewMode && event.key.toLowerCase() === 'n') reviewNext.click()
  else if (reviewMode && event.key.toLowerCase() === 'p') reviewPrevious.click()
  else if (reviewMode && event.shiftKey && event.key.toLowerCase() === 'c') void saveReviewCamera('manual', true).catch(handleError)
  else if (event.key.toLowerCase() === 'c') element('save-camera').click()
  else if (event.key.toLowerCase() === 's') element('save-segment').click()
  else if (event.key.toLowerCase() === 'k') element('save-crank').click()
})

const query = new URLSearchParams(location.search).get('video')
if (query === 'analysis' || query === '6dW6VYXp9HM') videoSelect.value = '6dW6VYXp9HM'
if (!import.meta.env.DEV) handleError('Alignment saves and private videos require the Vite development server.')
else {
  void loadMachine(scene).then(loadedMachine => {
    machine = loadedMachine
    if (machine.availability !== 'available') throw new Error(machine.loadError ?? 'CAD model unavailable. Run npm run fetch-model.')
    modelRoots.push(...scene.children.filter(object => object !== pivotMarker && !(object instanceof THREE.Light)))
    defaultPivot()
    rebaseControls()
    render()
  }).catch(handleError)
  void loadVideo().catch(handleError)
}
if (import.meta.env.DEV) Object.defineProperty(window, 'harmonicAlign', { value: {
  seek,
  hitTest(x: number, y: number) { return visibleModelPoint(x, y)?.toArray() ?? null },
  snapshot() { return { loaded, modelState: machine?.availability, videoId: videoSelect.value, t: original.currentTime, videoReadyState: original.readyState, shotId: currentShot?.id, viewId: currentView?.viewId, camera: cameraRecord(), pivot: pivot.toArray(), pivotSource, pivotRevision, rotationMode, input: serializeSyncInput(input), manual, review: { enabled: reviewMode, busy: reviewBusy, index: reviewIndex, total: reviewQueue.length, reviewed: reviewedCount, frame: reviewQueue[reviewIndex]?.frame, seedSource: reviewSeedSource } } },
} })
window.addEventListener('pagehide', () => { cancelAnimationFrame(renderFrame); controls.dispose(); pivotMarker.geometry.dispose(); pivotMarker.material.dispose(); machine?.dispose(); renderer.dispose(); environmentTarget.dispose() }, { once: true })
