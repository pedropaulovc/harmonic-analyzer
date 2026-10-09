import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
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
camera.lookAt(0, 0.68, 0)
let controls = new OrbitControls(camera, overlay)
controls.target.set(0, 0.68, 0)
controls.enableDamping = false
controls.addEventListener('change', render)
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
    renderFrame = 0
    if (!machine || !currentView) return
    try {
      machine.update(input)
      const rect = currentView.rectSourcePixels
      camera.aspect = rect[2] / rect[3]
      camera.fov = Number(fov.value)
      camera.setViewOffset(rect[2], rect[3], rect[2] / 2 - Number(ppX.value), rect[3] / 2 - Number(ppY.value), rect[2], rect[3])
      camera.updateProjectionMatrix()
      camera.updateMatrixWorld(true)
      const width = Math.max(1, Math.round(overlay.clientWidth)), height = Math.max(1, Math.round(overlay.clientHeight))
      renderer.setSize(width, height, false)
      renderer.render(scene, camera)
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : String(error)
      status.dataset.state = 'error'
    }
  })
}

function applyCamera(record: CameraRecord): void {
  camera.position.fromArray(record.positionMetres)
  camera.quaternion.fromArray(record.quaternion).normalize()
  camera.up.set(0, 1, 0).applyQuaternion(camera.quaternion)
  fov.value = String(record.verticalFovDegrees)
  ppX.value = String(record.principalPointViewportPixels?.[0] ?? (currentView?.rectSourcePixels[2] ?? 1920) / 2)
  ppY.value = String(record.principalPointViewportPixels?.[1] ?? (currentView?.rectSourcePixels[3] ?? 1080) / 2)
  const position = camera.position.clone(), quaternion = camera.quaternion.clone()
  const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(quaternion)
  const distance = Math.max(position.distanceTo(new THREE.Vector3(0, 0.68, 0)), 0.1)
  controls.dispose()
  controls = new OrbitControls(camera, overlay)
  controls.target.copy(position).addScaledVector(forward, distance)
  controls.enableDamping = false
  controls.update()
  // OrbitControls initializes by looking at its default target. Retain the
  // exact authored pose after rebasing its spherical state, including roll.
  camera.position.copy(position)
  camera.quaternion.copy(quaternion)
  controls.addEventListener('change', render)
}

function cameraRecord(): CameraRecord {
  return { positionMetres: camera.position.toArray() as [number, number, number], quaternion: camera.quaternion.toArray() as [number, number, number, number], verticalFovDegrees: Number(fov.value), principalPointViewportPixels: [Number(ppX.value), Number(ppY.value)] }
}

function reloadCamera(): void {
  if (!currentShot || !currentView) return
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
    camera.up.set(0, 1, 0)
    camera.lookAt(0, 0.68, 0)
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
for (const control of [fov, ppX, ppY]) control.addEventListener('input', render)
element<HTMLInputElement>('opacity').addEventListener('input', event => { overlay.style.opacity = (event.target as HTMLInputElement).value })
overlay.style.opacity = '0.5'
gearing.addEventListener('change', () => { input.gearing = gearing.value as MechanismInput['gearing']; render() })
magnification.addEventListener('input', () => { input.magnification = Number(magnification.value); render() })
crankControl.addEventListener('input', () => { input.crankTurns = Number(crankControl.value); render() })
for (const [id, control, delta] of [['pp-left', ppX, -1], ['pp-right', ppX, 1], ['pp-up', ppY, -1], ['pp-down', ppY, 1]] as const) {
  element(id).addEventListener('click', () => { control.value = String(Number(control.value) + delta); render() })
}
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
new ResizeObserver(render).observe(element('align-stage'))
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
    render()
  }).catch(handleError)
  void loadVideo().catch(handleError)
}
if (import.meta.env.DEV) Object.defineProperty(window, 'harmonicAlign', { value: {
  seek,
  snapshot() { return { loaded, modelState: machine?.availability, videoId: videoSelect.value, t: original.currentTime, videoReadyState: original.readyState, shotId: currentShot?.id, viewId: currentView?.viewId, camera: cameraRecord(), input: serializeSyncInput(input), manual, review: { enabled: reviewMode, busy: reviewBusy, index: reviewIndex, total: reviewQueue.length, reviewed: reviewedCount, frame: reviewQueue[reviewIndex]?.frame, seedSource: reviewSeedSource } } },
} })
window.addEventListener('pagehide', () => { cancelAnimationFrame(renderFrame); controls.dispose(); machine?.dispose(); renderer.dispose(); environmentTarget.dispose() }, { once: true })
