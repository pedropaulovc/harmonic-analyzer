import { assertSourceCompositeWeights, assertSourceCompositeProvenance, createViewer, loadMachine, ViewCapacityError, type CameraRecord, type Machine, type SourceView } from './scene'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_MAX, physicalChannelAngle, squareWave } from './kinematics'
import { VIDEOS, resolveVideo, type Video } from './video-catalog'
import { createVideoPlayer, type PlaybackState, type VideoPlayer } from './youtube-player'
import { loadReference, serializeInput, SOURCE_STAGE_PERCENTAGES, LANDMARK_LIMIT_PX, type PlaybackView, type ReferenceState } from './timeline'
import type { CompactVideoReference } from './source-track'
import { createSourceVideoPlayer } from './source-player'
import { INPUT_FIELDS, equalRecord, type InputField } from './source-witness'
import type { NativeDrawBinding } from './native-qualification-types'
import type { PartOverride } from './scene'
import type { NativeQualificationProducer, NativeQualificationCaptureContext, NativeQualificationByteSink } from './native-qualification-producer'
import { createNativeQualificationProducer } from './native-qualification-producer'
import { canonicalJson } from '../native-qualification-contract.mjs'

function element<T extends HTMLElement>(selector: string): T {
  const found = document.querySelector<T>(selector)
  if (!found) throw new Error(`Missing page element: ${selector}`)
  return found
}
const verificationEnabled = new URLSearchParams(location.search).get('verify') === '1'

const canvas = element<HTMLCanvasElement>('#stage')
const loading = element('#loading')
const modelStatus = element('#model-status')
const retryModel = element<HTMLButtonElement>('#retry-model')
const title = element('#video-title')
const playbackStatus = element('#playback-status')
const playbackClock = element('#playback-clock')
const sourceError = element('#source-error')
const modelError = element('#model-error')
const physicsError = element('#physics-error')
const videoError = element('#video-error')
element('.interaction-hint').textContent = 'Pause to orbit, pan, zoom, and change the mechanism. Play resumes approximate source-following with chosen feasible inputs, not recovered history. Unavailable intervals and unmeasured stages remain explicit.'
const videoContainer = element('#video-player')
const videoDock = element('#video-dock')
const workspace = element('#workspace')
const pauseButton = element<HTMLButtonElement>('#pause-video')
const followButton = element<HTMLButtonElement>('#follow-video')
const fitButton = element<HTMLButtonElement>('#fit-view')
const compactButton = element<HTMLButtonElement>('#minimize-player')
const driveControls = element<HTMLFieldSetElement>('#drive-controls')
const channelFieldset = element<HTMLFieldSetElement>('#channel-fieldset')
const crank = element<HTMLInputElement>('#crank')
const gearing = element<HTMLSelectElement>('#gearing')
const magnification = element<HTMLInputElement>('#magnification')
const fixture = element<HTMLInputElement>('#fixture-offset')
const cone = element<HTMLInputElement>('#cone-swing')
const pinion = element<HTMLInputElement>('#pinion-cam')
const platen = element<HTMLInputElement>('#platen-offset')
const manualRunButton = element<HTMLButtonElement>('#manual-run')
const speed = element<HTMLInputElement>('#crank-speed')
const forceReadout = element<HTMLOutputElement>('#force-readout')
const videoLabels: Record<string, string> = {
  NAsM30MAHLg: 'Intro / History', '8KmVDxkia_w': 'Synthesis',
  '6dW6VYXp9HM': 'Analysis', 'jfH-NbsmvD4': 'Operation',
  XPQwKRt4Y2k: 'Machine spin', '4mBuyixt22U': 'Rocker arms',
}
const stateLabels: Record<PlaybackState, string> = {
  unstarted: 'Ready to play', cued: 'Ready to play', playing: 'Playing', paused: 'Paused',
  buffering: 'Buffering', ended: 'Video ended', error: 'Playback unavailable',
}
const input = createMechanismInput()
const reviewRollbackInput = createMechanismInput()
let machine: Machine | null = null
let nativeQualificationProducer: NativeQualificationProducer | null = null
let nativeQualificationMachine: Machine | null = null
let nativeQualificationBusy = false
interface NativeFeatureMarker {
  id: string
  partPath: string
  partLocalMetres: [number, number, number]
  sourceFeatureEvidenceSHA256: string
  sourceVideoId: string
  timeSeconds: number
  viewId: string
}
let nativeFeatureMarkers: readonly NativeFeatureMarker[] = []
let reference: CompactVideoReference | null = null
let player: VideoPlayer | null = null
let video: Video | null = null
let selectionAbort: AbortController | null = null
let playbackState: PlaybackState = 'unstarted'
let mode: 'following-video' | 'exploring' | 'reference-review' = 'exploring'
let referenceSeek: 'idle' | 'seeking' = 'idle'
let referenceState: ReferenceState = 'unavailable'
let modelState: 'loading' | 'ready' | 'unavailable' = 'loading'
let modelTime = 0
let manualMotion: 'idle' | 'turning' = 'idle'
let manualRevision: 'pending' | 'clean' = 'pending'
let paintRevision: 'pending' | 'clean' = 'pending'
let physicsState: 'available' | 'unavailable' = 'unavailable'
let playerSize: 'expanded' | 'compact' = 'expanded'
let activeViews: readonly PlaybackView[] = []
let initialCamera: CameraRecord | null = null
let explorationOrigin: 'interactive-default' | 'chosen-feasible-reconstruction' = 'interactive-default'
const NO_PART_OVERRIDES: readonly PartOverride[] = []
interface MechanismDraw {
  status: 'solved-for-draw' | 'rendered'
  viewId: string
  timeSeconds: number
  sourceDrawRevision: number
  input: MechanismInput
  mechanicalProvenance: PlaybackView['mechanicalProvenance']
  unobservedInputFields: readonly InputField[]
  nativeGeometryAssumptions: PlaybackView['nativeGeometryAssumptions']
  imagePlaneWarp: PlaybackView['authoredImagePlaneWarp']
  resolvedImagePlaneWarp: NonNullable<PlaybackView['imagePlaneWarp']> | null
  sourceLayout: PlaybackView['sourceLayout']
  partOverrides: readonly PartOverride[]
  channelAnglesRad: Float64Array
  platenTravelM: number
  penTravelM: number
  effectiveBankDriveTurns: number
}
const mechanismDraws = new Map<string, MechanismDraw>()
let sourceDrawTimeSeconds = 0
let sourceDrawRevision = 0
let diagnosticReference: CompactVideoReference | null = null
let diagnosticMachine: Machine | null = null
let diagnosticFeatureTime: number | null = null
let lastTick = performance.now()
let lastHud = 0
const channelInputs: { amplitude: HTMLInputElement; phase: HTMLInputElement; value: HTMLOutputElement }[] = []

function notice(target: HTMLElement, message: string): void {
  if (target.textContent !== message) target.textContent = message
  target.hidden = message.length === 0
}

function copyInput(source: MechanismInput, target = input): void {
  target.crankTurns = source.crankTurns
  target.amplitudes.set(source.amplitudes)
  target.phases.set(source.phases)
  target.gearing = source.gearing
  target.magnification = source.magnification
  Object.assign(target.setup, source.setup)
}

function cameraRecord(): CameraRecord {
  return {
    positionMetres: viewer.camera.position.toArray() as [number, number, number],
    quaternion: viewer.camera.quaternion.toArray() as [number, number, number, number],
    verticalFovDegrees: viewer.camera.fov,
  }
}

function configureLandmarkProbe(): void {
  const enabled = verificationEnabled && mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused'
    && reference !== null && machine?.availability === 'available'
  const featureTime = nativeFeatureMarkers.some(marker => marker.sourceVideoId === video?.id && marker.timeSeconds === modelTime) ? modelTime : null
  if (enabled ? diagnosticReference === reference && diagnosticMachine === machine && diagnosticFeatureTime === featureTime : diagnosticReference === null && diagnosticMachine === null) return
  viewer.setNativeQualificationCaptureMode('disabled')
  if (!enabled) {
    nativeQualificationProducer?.dispose()
    nativeQualificationProducer = null
    nativeQualificationMachine = null
    nativeFeatureMarkers = []
  }
  viewer.setLandmarkProbe(null)
  viewer.setPartVisibilityProbe(null)
  diagnosticReference = null
  diagnosticMachine = null
  if (!enabled || !reference || machine?.availability !== 'available') return
  diagnosticReference = reference
  diagnosticMachine = machine
  diagnosticFeatureTime = featureTime
  const replacements = new Map(nativeFeatureMarkers.filter(marker => marker.sourceVideoId === video?.id && marker.timeSeconds === modelTime).map(marker => [marker.id, marker]))
  viewer.setLandmarkProbe(machine.createLandmarkProbe(reference.data.anchors.map(anchor => {
    const marker = replacements.get(anchor.id)
    if (!marker) return anchor
    const { worldMetres: _worldMetres, ...rest } = anchor
    return { ...rest, partPath: marker.partPath, partLocalMetres: marker.partLocalMetres }
  })))
}

function renderPending(): void {
  if (paintRevision === 'clean') return
  paintRevision = 'clean'
  viewer.render()
}

function updateMachine(source: MechanismInput, partOverrides: readonly PartOverride[] = NO_PART_OVERRIDES): void {
  if (machine?.availability !== 'available') return
  physicsState = 'unavailable'
  // Source names do not establish current native identity. Resolve every exact
  // authored target before changing any pose; retired paths remain unavailable.
  for (const override of partOverrides) {
    const path = override.partPath
    if (!machine.partPaths.includes(path)
      || !machine.nativeDrawablePartPaths.some(drawable => drawable === path || drawable.startsWith(`${path}/`))) {
      throw new Error(`Source part override has no actual current native drawable binding: ${path}`)
    }
  }
  machine.update(source, partOverrides)
  physicsState = 'available'
  paintRevision = 'pending'
}

function primaryView(): PlaybackView | undefined {
  let selected: PlaybackView | undefined
  let area = -1
  for (const view of activeViews) {
    const nextArea = view.rectSourcePixels[2] * view.rectSourcePixels[3] * (view.composite?.mode === 'crossfade' ? view.composite.opacity : 1)
    if (nextArea > 0 && nextArea > area) { area = nextArea; selected = view }
  }
  return selected
}

function updateControlState(): void {
  const editable = mode === 'exploring' && modelState === 'ready'
  driveControls.disabled = !editable
  channelFieldset.disabled = !editable
  fitButton.disabled = modelState !== 'ready' || mode !== 'exploring'
  followButton.disabled = modelState !== 'ready' || !reference
  pauseButton.disabled = !player
  pauseButton.textContent = playbackState === 'playing' || playbackState === 'buffering' ? 'Pause & explore' : 'Play video'
}

function validateSourceViews(views: readonly PlaybackView[]): void {
  if (machine?.availability !== 'available') throw new Error('A compatible native mechanism is required.')
  if (machine.missing.length) throw new Error(`Source reconstruction has unresolved native joints: ${machine.missing.join(', ')}.`)
  assertSourceCompositeWeights(views)
  for (const view of views) {
    assertSourceCompositeProvenance(view, true)
    if (!Object.hasOwn(view, 'authoredImagePlaneWarp') || !Object.hasOwn(view, 'sourceLayout')
      || view.authoredImagePlaneWarp === undefined || !Array.isArray(view.sourceLayout)
      || view.sourceLayout.length !== views.length
      || (view.authoredImagePlaneWarp !== null) !== (view.imagePlaneWarp !== undefined)) throw new Error(`Source view ${view.id} lacks explicit image-plane/layout metadata.`)
    for (let index = 0; index < views.length; index++) {
      const actual = views[index]!
      const entry = view.sourceLayout[index]!
      if (!entry || Object.keys(entry).length !== 6 || entry.viewId !== actual.id
        || !equalRecord(entry.rectSourcePixels, actual.rectSourcePixels)
        || entry.presentation !== actual.presentation || !equalRecord(entry.composite, actual.composite)
        || !Object.hasOwn(entry, 'compositeProvenance')
        || !equalRecord(entry.compositeProvenance, actual.compositeProvenance ?? null)
        || !Object.hasOwn(entry, 'resolvedImagePlaneWarp')
        || !equalRecord(entry.resolvedImagePlaneWarp, actual.imagePlaneWarp ?? null)) throw new Error(`Source view ${view.id} has stale or incomplete ordered source support.`)
    }
  }
}

function explore(): void {
  const chosen = primaryView()
  if (chosen && machine?.availability === 'available') {
    copyInput(chosen.input)
    updateMachine(input)
    viewer.applyCamera(chosen.camera)
    explorationOrigin = 'chosen-feasible-reconstruction'
  }
  activeViews = []
  mode = 'exploring'
  configureLandmarkProbe()
  manualMotion = 'idle'
  manualRunButton.textContent = 'Turn crank'
  viewer.setInteraction('exploring')
  updateControlState()
  updateHud()
  paintRevision = 'pending'
}

function following(): void {
  mode = 'following-video'
  configureLandmarkProbe()
  manualMotion = 'idle'
  manualRunButton.textContent = 'Turn crank'
  viewer.setInteraction('following-video')
  updateControlState()
}

function retryFollowing(): void {
  if (!player || mode !== 'exploring') return
  const state = player.getState()
  if (state !== 'playing' && state !== 'buffering') return
  try {
    renderSource(player.getTime())
    if (referenceState !== 'unavailable') following()
  } catch (error) { notice(physicsError, error instanceof Error ? error.message : String(error)) }
}

function applyView(view: PlaybackView, drawRevision: number): void {
  if (!machine || machine.availability !== 'available') return
  nativeQualificationProducer?.beginView(view.id, drawRevision)
  updateMachine(view.input, view.partOverrides ?? NO_PART_OVERRIDES)
  let draw = mechanismDraws.get(view.id)
  if (!draw) {
    draw = { status: 'solved-for-draw', viewId: view.id, timeSeconds: sourceDrawTimeSeconds, sourceDrawRevision: drawRevision,
      input: createMechanismInput(), mechanicalProvenance: view.mechanicalProvenance, unobservedInputFields: view.unobservedInputFields, nativeGeometryAssumptions: view.nativeGeometryAssumptions,
      imagePlaneWarp: view.authoredImagePlaneWarp, resolvedImagePlaneWarp: view.imagePlaneWarp ?? null, sourceLayout: view.sourceLayout, partOverrides: view.partOverrides ?? NO_PART_OVERRIDES,
      channelAnglesRad: new Float64Array(20), platenTravelM: 0, penTravelM: 0, effectiveBankDriveTurns: 0 }
    mechanismDraws.set(view.id, draw)
  }
  draw.status = 'solved-for-draw'
  draw.timeSeconds = sourceDrawTimeSeconds
  draw.sourceDrawRevision = drawRevision
  copyInput(machine.input, draw.input)
  draw.mechanicalProvenance = view.mechanicalProvenance
  draw.unobservedInputFields = view.unobservedInputFields
  draw.nativeGeometryAssumptions = view.nativeGeometryAssumptions
  draw.imagePlaneWarp = view.authoredImagePlaneWarp
  draw.resolvedImagePlaneWarp = view.imagePlaneWarp ?? null
  draw.sourceLayout = view.sourceLayout
  draw.partOverrides = view.partOverrides ?? NO_PART_OVERRIDES
  draw.channelAnglesRad.set(machine.pose.channelAnglesRad)
  draw.platenTravelM = machine.pose.platenTravelM
  draw.penTravelM = machine.pose.magnifier.penTravelM
  draw.effectiveBankDriveTurns = (machine.pose.channelAnglesRad[19]! - machine.input.phases[19]!) / physicalChannelAngle(1, 19)
}

function drawSourceViews(views: readonly PlaybackView[], timeSeconds: number): void {
  sourceDrawTimeSeconds = timeSeconds
  try {
    sourceDrawRevision = viewer.renderViews(views, beforeView, timeSeconds)
  } catch (error) {
    // No physical receipt remains rendered when the source batch did not complete.
    for (const draw of mechanismDraws.values()) draw.status = 'solved-for-draw'
    throw error
  }
  for (const view of views) {
    const draw = mechanismDraws.get(view.id)
    if (draw?.sourceDrawRevision === sourceDrawRevision) draw.status = 'rendered'
  }
}

function renderedMechanism(viewId: string) {
  const draw = mechanismDraws.get(viewId)
  if (!draw) return { status: 'unavailable' as const, viewId, imagePlaneWarp: null, resolvedImagePlaneWarp: null, sourceLayout: [] }
  return {
    status: mode === 'exploring' || referenceState === 'unavailable' || draw.timeSeconds !== modelTime || draw.sourceDrawRevision !== sourceDrawRevision ? 'stale' as const : draw.status,
    viewId, timeSeconds: draw.timeSeconds, sourceDrawRevision: draw.sourceDrawRevision,
    method: 'actual-native-mechanism-solve' as const, input: serializeInput(draw.input),
    mechanicalProvenance: draw.mechanicalProvenance, unobservedInputFields: draw.unobservedInputFields,
    nativeGeometryAssumptions: draw.nativeGeometryAssumptions,
    imagePlaneWarp: draw.imagePlaneWarp, resolvedImagePlaneWarp: draw.resolvedImagePlaneWarp, sourceLayout: draw.sourceLayout, partOverrides: draw.partOverrides,
    channelAnglesRad: Array.from(draw.channelAnglesRad), platenTravelM: draw.platenTravelM, penTravelM: draw.penTravelM, effectiveBankDriveTurns: draw.effectiveBankDriveTurns,
  }
}

function sourceCapture<T extends {
  status: string
  viewId: string
  drawRevision: number | null
  timeSeconds: number | null
  resolvedImagePlaneWarp: NonNullable<PlaybackView['imagePlaneWarp']> | null
  sourceLayout: PlaybackView['sourceLayout']
}>(capture: T) {
  const draw = mechanismDraws.get(capture.viewId)
  const bound = draw?.status === 'rendered' && draw.timeSeconds === capture.timeSeconds
    && capture.drawRevision === draw.sourceDrawRevision && draw.sourceDrawRevision === sourceDrawRevision
    && equalRecord(draw.resolvedImagePlaneWarp, capture.resolvedImagePlaneWarp)
    && equalRecord(draw.sourceLayout, capture.sourceLayout)
  return {
    ...capture,
    status: capture.status === 'captured' && (mode !== 'reference-review' || referenceSeek !== 'idle' || player?.getState() !== 'paused') ? 'unavailable' as const
      : capture.status === 'captured' && (!bound || referenceState === 'unavailable' || capture.timeSeconds !== modelTime) ? 'stale' as const : capture.status,
    imagePlaneWarp: bound ? draw.imagePlaneWarp : null,
  }
}


function renderSource(timeSeconds: number): void {
  configureLandmarkProbe()
  if (!reference || !machine || machine.availability !== 'available') {
    referenceState = 'unavailable'
    renderPending()
    return
  }
  const prepared = reference.prepareAt(timeSeconds)
  if (prepared.state !== 'unavailable') {
    validateSourceViews(prepared.views)
    viewer.preflightViews(prepared.views)
  }
  const sample = reference.commitPrepared()
  referenceState = sample.state
  activeViews = sample.views
  if (sample.state === 'unavailable') {
    notice(sourceError, sample.reason)
    renderPending()
    return
  }
  if (sample.views.length === 0) {
    renderPending()
  } else {
    const chosen = primaryView()
    if (chosen) copyInput(chosen.input)
    drawSourceViews(sample.views, timeSeconds)
    paintRevision = 'clean'
  }
  modelTime = timeSeconds
  notice(physicsError, '')
  notice(sourceError, reference.approximationMessage)
}

function beforeView(_view: SourceView, index: number, drawRevision: number): void {
  const sample = activeViews[index]
  if (sample) applyView(sample, drawRevision)
}

function updateHud(): void {
  const time = player?.getTime() ?? 0
  const chosen = mode === 'exploring' ? undefined : primaryView()
  const context = mode === 'exploring'
    ? explorationOrigin === 'chosen-feasible-reconstruction' ? 'Manual exploration from chosen feasible reconstruction (not recovered history)' : 'Manual exploration'
    : referenceState === 'approximate' ? 'Approximate source-following; chosen inputs, not recovered history or a final matched result'
      : referenceState === 'no-machine' ? 'No corresponding machine in this source interval' : 'Source pose unavailable'
  const hidden = chosen?.unobservedInputFields ?? []
  const valueLabel = (field: InputField, value: string): string => `${value}${hidden.includes(field) ? ' · chosen, not measured' : mode !== 'exploring' && !chosen ? ' · not source-measured' : ''}`
  const markControl = (control: HTMLInputElement | HTMLSelectElement, field: InputField): void => {
    const provenance = mode === 'exploring' ? 'manual' : !chosen ? 'unobserved' : hidden.includes(field) ? 'chosen' : 'measured'
    control.dataset.provenance = provenance
    control.title = provenance === 'chosen' ? 'Chosen physically feasible input; source setting unobserved, not measured.' : provenance === 'manual' ? 'Manual physical input; not a source measurement.' : provenance === 'unobserved' ? 'Source setting unobserved; retained physical input is not measured.' : 'Source-measured input.'
  }
  markControl(crank, 'crankTurns')
  markControl(gearing, 'gearing')
  markControl(magnification, 'magnification')
  markControl(fixture, 'setup.wireFixtureOffsetM')
  markControl(cone, 'setup.coneSwingRad')
  markControl(pinion, 'setup.pinionCamRad')
  markControl(platen, 'setup.platenOffsetM')
  let geometryAssumption = ''
  if (reference?.data.nativeGeometryAssumptions) for (const assumption of reference.data.nativeGeometryAssumptions) {
    geometryAssumption += assumption.id === 'rod-head-functional-equivalence'
      ? ' · Rod-head topology assumed pending CAD match; not geometric-fidelity passed'
      : ' · Two lower-rocker side-face features absent and uncertified; narrow functional exception, not geometric-fidelity passed'
  }
  const announcedStatus = `${stateLabels[playbackState]} · ${context}${geometryAssumption}`
  if (playbackStatus.textContent !== announcedStatus) playbackStatus.textContent = announcedStatus
  const clock = ` · ${time.toFixed(1)} s`
  if (playbackClock.textContent !== clock) playbackClock.textContent = clock
  crank.value = String(input.crankTurns)
  element<HTMLOutputElement>('#crank-value').value = valueLabel('crankTurns', `${input.crankTurns.toFixed(3)} turns`)
  gearing.value = input.gearing
  magnification.value = String(input.magnification)
  fixture.value = String(input.setup.wireFixtureOffsetM)
  cone.value = String(input.setup.coneSwingRad)
  pinion.value = String(input.setup.pinionCamRad)
  platen.value = String(input.setup.platenOffsetM)
  element<HTMLOutputElement>('#magnification-value').value = valueLabel('magnification', `${input.magnification.toFixed(3)}×`)
  element<HTMLOutputElement>('#fixture-value').value = valueLabel('setup.wireFixtureOffsetM', `${(input.setup.wireFixtureOffsetM * 1000).toFixed(1)} mm`)
  element<HTMLOutputElement>('#cone-value').value = valueLabel('setup.coneSwingRad', `${(input.setup.coneSwingRad * 180 / Math.PI).toFixed(2)}°`)
  element<HTMLOutputElement>('#pinion-value').value = valueLabel('setup.pinionCamRad', `${(input.setup.pinionCamRad * 180 / Math.PI).toFixed(1)}°`)
  element<HTMLOutputElement>('#platen-value').value = valueLabel('setup.platenOffsetM', `${(input.setup.platenOffsetM * 1000).toFixed(1)} mm`)
  for (let i = 0; i < channelInputs.length; i++) {
    const controls = channelInputs[i]!
    controls.amplitude.value = String(input.amplitudes[i]!)
    controls.phase.value = String(input.phases[i]! * 180 / Math.PI)
    markControl(controls.amplitude, `amplitudes[${i}]`)
    markControl(controls.phase, `phases[${i}]`)
    controls.value.value = `${valueLabel(`amplitudes[${i}]`, `${(input.amplitudes[i]! * MECHANISM_DATA.channel.maximumStationMm).toFixed(1)} mm`)} · ${valueLabel(`phases[${i}]`, `${(input.phases[i]! * 180 / Math.PI).toFixed(0)}°`)}`
  }
  if (!machine || machine.availability !== 'available' || physicsState !== 'available') {
    forceReadout.value = modelState === 'ready' ? 'Mechanical state rejected; last rendered geometry retained.' : 'No compatible CAD mechanical state available.'
    return
  }
  let minimum = Infinity
  let maximum = -Infinity
  for (const force of machine.pose.springForcesN) {
    minimum = Math.min(minimum, force)
    maximum = Math.max(maximum, force)
  }
  const forceView = mode === 'exploring' ? undefined : activeViews[activeViews.length - 1]
  const forceProvenance = mode === 'exploring' ? 'Manual physical calculation — not source measurements' : forceView ? 'Chosen-input physical calculation — not source measurements' : 'Last physical calculation — source reconstruction unavailable, not source-measured'
  const counterChoice = forceView?.unobservedInputFields.includes('setup.counterHeightM') ? `\nCounter ${forceView.input.setup.counterHeightM === null ? 'auto-level algorithm' : 'height'} chosen, not measured` : ''
  forceReadout.value = `${forceProvenance}${forceView ? ` · view ${forceView.id}` : ''}\n20 springs · ${minimum.toFixed(2)}–${maximum.toFixed(2)} N\nTorque residual ${machine.pose.equilibriumResidualNm.toExponential(1)} N·m\nPaper feed ${(machine.pose.platenTravelM * 1000).toFixed(2)} mm${counterChoice}`
}

function editMechanism(action: () => void): void {
  if (mode !== 'exploring' || modelState !== 'ready') return
  action()
  manualRevision = 'pending'
  updateHud()
}

function buildChannelControls(): void {
  const container = element('#channel-controls')
  for (let i = 0; i < 20; i++) {
    const harmonic = MECHANISM_DATA.harmonicNumbers[i]!
    const row = document.createElement('div')
    row.className = 'channel-row'
    const heading = document.createElement('span')
    heading.textContent = `H${harmonic}`
    const amplitude = document.createElement('input')
    amplitude.id = `amplitude-${harmonic}`
    amplitude.type = 'range'
    amplitude.min = '-1'
    amplitude.max = '1'
    amplitude.step = '0.001'
    amplitude.setAttribute('aria-label', `Harmonic ${harmonic} amplitude`)
    const phase = document.createElement('input')
    phase.id = `phase-${harmonic}`
    phase.type = 'range'
    phase.min = '-180'
    phase.max = '180'
    phase.step = '1'
    phase.setAttribute('aria-label', `Harmonic ${harmonic} cam phase in degrees`)
    const value = document.createElement('output')
    value.setAttribute('for', `${amplitude.id} ${phase.id}`)
    row.append(heading, amplitude, phase, value)
    amplitude.addEventListener('input', () => editMechanism(() => { input.amplitudes[i] = Number(amplitude.value) }))
    phase.addEventListener('input', () => editMechanism(() => { input.phases[i] = Number(phase.value) * Math.PI / 180 }))
    container.append(row)
    channelInputs.push({ amplitude, phase, value })
  }
}

function buildVideoNavigation(): void {
  const navigation = element('#videos')
  for (const entry of VIDEOS) {
    const link = document.createElement('a')
    const route = new URL(location.href)
    route.searchParams.set('video', entry.slug)
    link.href = route.href
    link.dataset.videoId = entry.id
    link.textContent = videoLabels[entry.id]!
    link.title = entry.title
    link.addEventListener('click', (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      history.pushState(null, '', link.href)
      void selectVideo(entry)
    })
    navigation.append(link)
  }
}

async function selectVideo(next: Video): Promise<void> {
  selectionAbort?.abort()
  const selection = new AbortController()
  selectionAbort = selection
  player?.destroy()
  player = null
  reference = null
  activeViews = []
  explorationOrigin = 'interactive-default'
  configureLandmarkProbe()
  referenceSeek = 'idle'
  video = next
  videoContainer.replaceChildren()
  playbackState = 'unstarted'
  referenceState = 'unavailable'
  modelTime = 0
  copyInput(createMechanismInput())
  manualRevision = 'pending'
  mode = 'exploring'
  viewer.setInteraction('exploring')
  if (initialCamera) viewer.applyCamera(initialCamera)
  title.textContent = videoLabels[next.id]!
  document.title = `${videoLabels[next.id]} — Harmonic Analyzer`
  element('#video-label').textContent = videoLabels[next.id]!
  const external = element<HTMLAnchorElement>('#watch-on-youtube')
  external.href = `https://www.youtube.com/watch?v=${next.id}`
  for (const link of element('#videos').querySelectorAll<HTMLAnchorElement>('a')) {
    if (link.dataset.videoId === next.id) link.setAttribute('aria-current', 'page')
    else link.removeAttribute('aria-current')
  }
  notice(videoError, '')
  notice(sourceError, '')
  notice(physicsError, '')
  updateControlState()
  const sourcePromise = loadReference(next).then((loaded) => {
    if (selection.signal.aborted) return
    reference = loaded
    if (loaded.data.coverage.status === 'blocked') notice(sourceError, `Source coverage is not complete: ${loaded.coverageMessage}`)
    configureLandmarkProbe()
  }).catch((error: unknown) => {
    if (!selection.signal.aborted) notice(sourceError, error instanceof Error ? error.message : String(error))
  })
  try {
    const createPlayer = new URLSearchParams(location.search).get('referenceMedia') === '1' ? createSourceVideoPlayer : createVideoPlayer
    const created = await createPlayer(videoContainer, next.id, (state) => {
      if (selection.signal.aborted) return
      playbackState = state
      if (state === 'playing') {
        notice(videoError, '')
        if (mode === 'reference-review' && referenceSeek === 'seeking') player?.pause()
        else {
          try { renderSource(player?.getTime() ?? 0); if (referenceState !== 'unavailable') following() }
          catch (error) { notice(physicsError, error instanceof Error ? error.message : String(error)) }
        }
      } else if ((state === 'paused' || state === 'ended') && mode !== 'reference-review') {
        explore()
      }
      updateControlState()
    }, {
      signal: selection.signal,
      onError: (error) => { if (!selection.signal.aborted) notice(videoError, error.message) },
    })
    if (selection.signal.aborted) { created.destroy(); return }
    player = created
    playbackState = created.getState()
    updateControlState()
  } catch (error) {
    if (!selection.signal.aborted) notice(videoError, error instanceof Error ? error.message : String(error))
  }
  await sourcePromise
  if (!selection.signal.aborted) { retryFollowing(); updateControlState(); updateHud() }
}

function selectRoute(): void {
  try { void selectVideo(resolveVideo(location.search)) }
  catch (error) {
    selectionAbort?.abort()
    player?.destroy()
    player = null
    video = null
    reference = null
    activeViews = []
    configureLandmarkProbe()
    mode = 'exploring'
    viewer.setInteraction('exploring')
    title.textContent = 'Unknown video'
    notice(videoError, error instanceof Error ? error.message : String(error))
    updateControlState()
  }
}

async function fetchMachine(): Promise<void> {
  modelState = 'loading'
  physicsState = 'unavailable'
  loading.hidden = false
  retryModel.hidden = true
  updateControlState()
  try {
    machine = await loadMachine(viewer.scene)
    if (machine.availability !== 'available') throw new Error(machine.loadError ?? 'The CAD model is unavailable.')
    modelState = 'ready'
    updateMachine(input)
    viewer.fitView()
    initialCamera = cameraRecord()
    loading.hidden = true
    modelStatus.textContent = `Lossless Meshopt model loaded (${machine.provenance.observedSha256?.slice(0, 12)}; ${machine.provenance.observedByteLength} bytes). Native CAD source ${machine.provenance.sourceSha256.slice(0, 12)} @ ${machine.provenance.sourceCommit.slice(0, 12)}; loading does not qualify source calibration.`
    notice(modelError, machine.missing.length ? `Unresolved native joints: ${machine.missing.join(', ')}. This model cannot establish complete footage fidelity.` : '')
    configureLandmarkProbe()
    manualRevision = 'clean'
    retryFollowing()
  } catch (error) {
    modelState = 'unavailable'
    modelStatus.textContent = `No compatible model loaded. Run npm run fetch-model -- path/to/released.glb. ${error instanceof Error ? error.message : String(error)}`
    notice(modelError, error instanceof Error ? error.message : String(error))
    retryModel.hidden = false
  }
  updateControlState()
  updateHud()
}

function tick(now: number): void {
  requestAnimationFrame(tick)
  const elapsed = Math.min((now - lastTick) / 1000, 0.25)
  lastTick = now
  try {
    if (mode === 'following-video' && player) {
      renderSource(player.getTime())
    } else if (mode === 'exploring') {
      if (manualMotion === 'turning') {
        input.crankTurns += elapsed * Number(speed.value)
        manualRevision = 'pending'
      }
      if (manualRevision === 'pending' && machine?.availability === 'available') {
        updateMachine(input)
        manualRevision = 'clean'
        notice(physicsError, '')
      }
      if (paintRevision === 'pending') renderPending()
      else viewer.controls.update()
    } else if (paintRevision === 'pending') {
      if (activeViews.length) drawSourceViews(activeViews, modelTime)
      else renderPending()
      paintRevision = 'clean'
    }
  } catch (error) {
    notice(physicsError, error instanceof Error ? error.message : String(error))
    if (!(error instanceof ViewCapacityError)) {
      // Unforeseeable draw/solver failures remain fail closed. A predictable
      // pre-commit capacity refusal leaves the last accepted native frame alone.
      manualMotion = 'idle'
      manualRevision = 'clean'
      physicsState = 'unavailable'
      manualRunButton.textContent = 'Turn crank'
      referenceState = 'unavailable'
      renderPending()
    }
  }
  if (now - lastHud >= 100) { updateHud(); lastHud = now }
}

const viewer = createViewer(canvas, () => { paintRevision = 'pending' })
new ResizeObserver(() => { paintRevision = 'pending' }).observe(canvas.parentElement!)
buildVideoNavigation()
buildChannelControls()
magnification.min = String(MAGNIFIER_RATIO_MIN)
magnification.max = String(MAGNIFIER_RATIO_MAX)
fixture.min = String(MECHANISM_DATA.magnifier.fixtureOffsetRangeM[0])
fixture.max = String(MECHANISM_DATA.magnifier.fixtureOffsetRangeM[1])
cone.min = '0'
cone.max = String(MECHANISM_DATA.setup.coneDisengageRad)
pinion.min = String(MECHANISM_DATA.setup.pinionEngageCamRad)
pinion.max = '0'
crank.addEventListener('input', () => editMechanism(() => { input.crankTurns = Number(crank.value); manualMotion = 'idle'; manualRunButton.textContent = 'Turn crank' }))
gearing.addEventListener('change', () => editMechanism(() => { input.gearing = gearing.value as MechanismInput['gearing'] }))
magnification.addEventListener('input', () => editMechanism(() => { input.magnification = Number(magnification.value) }))
fixture.addEventListener('input', () => editMechanism(() => { input.setup.wireFixtureOffsetM = Number(fixture.value) }))
cone.addEventListener('input', () => editMechanism(() => {
  const nextSwing = Number(cone.value)
  if (input.setup.coneSwingRad === 0 && nextSwing !== 0) {
    input.setup.heldChannelTurns = input.crankTurns - input.setup.driveCrankOffsetTurns
  }
  if (input.setup.coneSwingRad !== 0 && nextSwing === 0) {
    input.setup.driveCrankOffsetTurns = input.crankTurns - input.setup.heldChannelTurns
  }
  input.setup.coneSwingRad = nextSwing
}))
pinion.addEventListener('input', () => editMechanism(() => { input.setup.pinionCamRad = Number(pinion.value) }))
platen.addEventListener('input', () => editMechanism(() => { input.setup.platenOffsetM = Number(platen.value) }))
manualRunButton.addEventListener('click', () => {
  if (mode !== 'exploring') return
  manualMotion = manualMotion === 'idle' ? 'turning' : 'idle'
  manualRunButton.textContent = manualMotion === 'turning' ? 'Stop crank' : 'Turn crank'
})
element<HTMLButtonElement>('#zero-coefficients').addEventListener('click', () => editMechanism(() => { input.amplitudes.fill(0) }))
element<HTMLButtonElement>('#fundamental-coefficient').addEventListener('click', () => editMechanism(() => {
  for (let i = 0; i < 20; i++) input.amplitudes[i] = MECHANISM_DATA.harmonicNumbers[i] === 1 ? 0.4 : 0
}))
element<HTMLButtonElement>('#odd-coefficients').addEventListener('click', () => editMechanism(() => {
  const coefficients = squareWave(6)
  for (let i = 0; i < 20; i++) input.amplitudes[i] = coefficients[MECHANISM_DATA.harmonicNumbers[i]! - 1]! / 10
}))
pauseButton.addEventListener('click', () => {
  if (player?.getState() === 'playing' || player?.getState() === 'buffering') player.pause()
  else player?.play()
})
followButton.addEventListener('click', () => {
  if (!player) return
  try {
    renderSource(player.getTime())
    if (referenceState === 'unavailable') return
    if (player.getState() !== 'playing' && player.getState() !== 'buffering') explore()
    else following()
  } catch (error) { notice(physicsError, error instanceof Error ? error.message : String(error)) }
})
fitButton.addEventListener('click', () => { if (mode === 'exploring') viewer.fitView() })
compactButton.addEventListener('click', () => {
  playerSize = playerSize === 'expanded' ? 'compact' : 'expanded'
  videoDock.dataset.size = playerSize
  workspace.dataset.playerSize = playerSize
  compactButton.textContent = playerSize === 'compact' ? 'Expand player' : 'Compact player'
  compactButton.setAttribute('aria-expanded', String(playerSize === 'expanded'))
  viewer.resize()
  paintRevision = 'pending'
})
retryModel.addEventListener('click', () => { void fetchMachine() })
window.addEventListener('popstate', selectRoute)

if (verificationEnabled) {
  const bridge = {
    snapshot() {
      const chosen = mode === 'exploring' ? undefined : primaryView()
      return {
        videoId: video?.id ?? null, playerVideoId: player?.getVideoId() ?? null, mode, playerState: player?.getState() ?? playbackState,
        videoTime: player?.getTime() ?? null, modelTime, referenceState, modelState, missingBindings: machine?.missing ?? [],
        modelProvenance: machine?.provenance ?? null, camera: cameraRecord(), input: serializeInput(input),
        sourceDrawRevision, sourceDrawTimeSeconds, diagnosticCapture: diagnosticReference !== null && diagnosticReference === reference && diagnosticMachine === machine && mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused' ? 'paused-reference-review' : 'disabled',
        sourceFollowing: reference ? { kind: reference.kind, stageLadder: SOURCE_STAGE_PERCENTAGES, finalTolerancePx: LANDMARK_LIMIT_PX, stages: reference.stageStatus, stageEvidence: 'unmeasured: no independently bound rendered report loaded', sourceMeasurements: reference.data.sourceMeasurements ?? null } : null,
        imagePlaneWarp: chosen ? chosen.authoredImagePlaneWarp : null,
        resolvedImagePlaneWarp: chosen?.imagePlaneWarp ?? null,
        sourceLayout: chosen?.sourceLayout ?? [],
        mechanicalProvenance: mode === 'exploring' ? null : primaryView()?.mechanicalProvenance ?? null,
        unobservedInputFields: mode === 'exploring' ? INPUT_FIELDS : primaryView()?.unobservedInputFields ?? INPUT_FIELDS,
        explorationOrigin, inputMeaning: mode === 'exploring' ? 'manual-physical-input' : !primaryView() ? 'unverified-retained-physical-input' : 'chosen-feasible-approximation',
        nativeGeometryAssumptions: reference?.data.nativeGeometryAssumptions ?? [],
        physics: machine && physicsState === 'available' ? { renderedViewId: mode === 'exploring' ? 'exploring' : activeViews[activeViews.length - 1]?.id ?? null, mechanicalProvenance: mode === 'exploring' ? null : activeViews[activeViews.length - 1]?.mechanicalProvenance ?? null, springForcesN: Array.from(machine.pose.springForcesN), springLengthsM: Array.from(machine.pose.springLengthsM), equilibriumResidualNm: machine.pose.equilibriumResidualNm, platenTravelM: machine.pose.platenTravelM, summingAngleRad: machine.pose.summingAngleRad } : null,
        playerAudio: player?.getAudio() ?? null,
        views: activeViews.map((view) => ({ id: view.id, rectSourcePixels: view.rectSourcePixels, presentation: view.presentation, composite: view.composite, compositeProvenance: view.compositeProvenance, imagePlaneWarp: view.authoredImagePlaneWarp, resolvedImagePlaneWarp: view.imagePlaneWarp ?? null, sourceLayout: view.sourceLayout, camera: view.camera, input: serializeInput(view.input), mechanicalProvenance: view.mechanicalProvenance, unobservedInputFields: view.unobservedInputFields, sourceSampling: view.sourceSampling, nativeGeometryAssumptions: view.nativeGeometryAssumptions, partOverrides: view.partOverrides ?? NO_PART_OVERRIDES, renderedMechanism: renderedMechanism(view.id) })),
      }
    },
    compactData() { return reference?.data ?? null },
    pauseVideo() { player?.pause(); return this.snapshot() },
    playVideo() { player?.play(); return this.snapshot() },
    async reviewReferenceFrame(timeSeconds: number, sourceTimeSeconds = timeSeconds) {
      const nativePlayer = player
      if (nativePlayer?.getState() !== 'paused') throw new Error('Pause the actual source video before reviewing a reference frame.')
      if (!reference) throw new Error('Source observations are unavailable.')
      if (physicsState !== 'available') throw new Error('Restore a valid mechanical setup before reviewing a source frame.')
      if (referenceSeek === 'seeking') throw new Error('A native reference seek is already active.')
      if (!Number.isFinite(timeSeconds) || timeSeconds < 0) throw new Error('Reference time must be finite and nonnegative.')
      if (!Number.isFinite(sourceTimeSeconds) || sourceTimeSeconds < 0 || Math.abs(sourceTimeSeconds - timeSeconds) > 0.5) throw new Error('Decoded source review time must be within 0.5s of its model sample.')
      if (reference.getState(timeSeconds) === 'unavailable') throw new Error('The requested source frame has no available corresponding camera and feasible pose.')
      const previousView = mode === 'exploring' ? undefined : primaryView()
      const sourceCamera = previousView?.camera ?? cameraRecord()
      const previousCamera: CameraRecord = {
        positionMetres: [...sourceCamera.positionMetres],
        quaternion: [...sourceCamera.quaternion],
        verticalFovDegrees: sourceCamera.verticalFovDegrees,
      }
      const prepared = reference.prepareAt(timeSeconds)
      validateSourceViews(prepared.views)
      viewer.preflightViews(prepared.views)
      copyInput(input, reviewRollbackInput)
      try {
        mode = 'reference-review'
        referenceSeek = 'seeking'
        viewer.setInteraction('following-video')
        updateControlState()
        const sourceMedia = videoContainer.querySelector('video')
        const seekTime = sourceMedia && sourceTimeSeconds >= sourceMedia.duration && sourceTimeSeconds - sourceMedia.duration <= 0.5 ? Math.max(0, sourceMedia.duration - 1e-6) : sourceTimeSeconds
        nativePlayer.seek(seekTime)
        await new Promise<void>((resolve) => window.setTimeout(resolve, 40))
        const deadline = performance.now() + 20_000
        while (nativePlayer.getState() !== 'paused' || Math.abs(nativePlayer.getTime() - seekTime) > 0.002 || sourceMedia && (sourceMedia.seeking || sourceMedia.readyState < HTMLMediaElement.HAVE_CURRENT_DATA)) {
          if (nativePlayer !== player) throw new Error('The source video changed during reference review.')
          if (nativePlayer.getState() === 'error' || nativePlayer.getState() === 'ended') throw new Error('The actual source video cannot display the requested reference time.')
          if (performance.now() >= deadline) throw new Error('The actual source video did not settle at the requested paused reference time.')
          await new Promise<void>((resolve) => window.setTimeout(resolve, 40))
        }
        if (nativePlayer !== player) throw new Error('The source video changed during reference review.')
        referenceSeek = 'idle'
        renderSource(timeSeconds)
        if (referenceState === 'unavailable') throw new Error('The requested source frame has no available corresponding camera and feasible pose.')
        return this.snapshot()
      } catch (error) {
        if (nativePlayer === player) {
          referenceSeek = 'idle'
          mode = 'exploring'
          configureLandmarkProbe()
          activeViews = []
          referenceState = 'unavailable'
          copyInput(reviewRollbackInput)
          updateMachine(input)
          viewer.applyCamera(previousCamera)
          viewer.setInteraction('exploring')
          nativePlayer.pause()
          notice(physicsError, error instanceof Error ? error.message : String(error))
          updateControlState()
        }
        throw error
      }
    },
    endReferenceReview() {
      if (player?.getState() !== 'paused') throw new Error('Pause the actual source video before entering manual exploration.')
      if (referenceSeek === 'seeking') throw new Error('Wait for the active native reference seek before entering manual exploration.')
      explore()
      return this.snapshot()
    },
    renderedLandmarks(viewId: string) {
      if (mode !== 'reference-review' || referenceSeek !== 'idle' || player?.getState() !== 'paused') return null
      const capture = viewer.readRenderedLandmarks(viewId)
      return capture ? sourceCapture(capture) : null
    },
    renderedPartVisibility(viewId: string) {
      const capture = sourceCapture(viewer.readRenderedPartVisibility(viewId))
      return mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused' ? capture : { ...capture, status: 'unavailable' as const, parts: [] }
    },
    enablePartVisibility() {
      if (mode !== 'reference-review' || referenceSeek !== 'idle' || player?.getState() !== 'paused') throw new Error('Pause and review an actual source frame before enabling native visibility capture.')
      configureLandmarkProbe()
      if (machine?.availability !== 'available') throw new Error('A compatible native mechanism is required.')
      viewer.setPartVisibilityProbe(machine.createPartVisibilityProbe())
      if (activeViews.length) drawSourceViews(activeViews, modelTime)
    },
    async enableNativeQualification(options: { featureMarkers?: readonly NativeFeatureMarker[] } = {}) {
      if (mode !== 'reference-review' || referenceSeek !== 'idle' || player?.getState() !== 'paused' || machine?.availability !== 'available') throw new Error('Native qualification requires a paused current original source frame and compatible native mechanism.')
      if (nativeQualificationBusy) throw new Error('A native byte capture is active.')
      const currentMachine = machine
      if (options.featureMarkers && !equalRecord(options.featureMarkers, nativeFeatureMarkers)) {
        for (const marker of options.featureMarkers) {
          if (!reference?.data.anchors.some(anchor => anchor.id === marker.id) || marker.sourceVideoId !== video?.id
            || !Number.isFinite(marker.timeSeconds) || !marker.viewId || !marker.partPath.startsWith('harmonic-analyzer/')
            || marker.partLocalMetres.length !== 3 || !marker.partLocalMetres.every(Number.isFinite)
            || !/^[a-f0-9]{64}$/.test(marker.sourceFeatureEvidenceSHA256)) throw new Error('Native marker lacks its original source/physical feature binding.')
        }
        nativeFeatureMarkers = options.featureMarkers
        diagnosticReference = null
      }
      configureLandmarkProbe()
      if (!nativeQualificationProducer || nativeQualificationMachine !== currentMachine) {
        nativeQualificationProducer?.dispose()
        nativeQualificationProducer = createNativeQualificationProducer({ machine: currentMachine, viewer })
        nativeQualificationMachine = currentMachine
      }
      if (!activeViews.length || viewer.readRenderedPartVisibility(activeViews[0]!.id).status !== 'captured') {
        viewer.setNativeQualificationCaptureMode('disabled')
        viewer.setPartVisibilityProbe(currentMachine.createPartVisibilityProbe())
      }
      viewer.setNativeQualificationCaptureMode('enabled')
      nativeQualificationProducer.enableCapture()
      drawSourceViews(activeViews, modelTime)
      return this.snapshot()
    },
    nativeQualificationState(viewId: string) {
      const capture = sourceCapture(viewer.readNativeQualificationCapture(viewId))
      return {
        status: capture.status, reason: capture.reason, viewId: capture.viewId, drawRevision: capture.drawRevision,
        completedDrawEpoch: capture.completedDrawEpoch, timeSeconds: capture.timeSeconds, camera: capture.camera,
        rectSourcePixels: capture.rectSourcePixels, presentation: capture.presentation, sourceOpacity: capture.sourceOpacity,
        imagePlaneWarp: capture.imagePlaneWarp, resolvedImagePlaneWarp: capture.resolvedImagePlaneWarp, sourceLayout: capture.sourceLayout,
        nativeViewportBackingPixels: capture.nativeViewportBackingPixels, destinationCellSourcePixels: capture.destinationCellSourcePixels,
        sourceStageViewportBackingPixels: capture.sourceStageViewportBackingPixels, sourceStageScissorBackingPixels: capture.sourceStageScissorBackingPixels,
      }
    },
    async captureNativeQualification(request: { binding: NativeDrawBinding; sinkEndpoint: string; context: Omit<NativeQualificationCaptureContext, 'sceneCapture'> }) {
      if (!nativeQualificationProducer || nativeQualificationMachine !== machine || nativeQualificationBusy) throw new Error('Enable a native capture before requesting one unique source view.')
      const producer = nativeQualificationProducer
      const binding = request.binding
      const validate = () => {
        const capture = sourceCapture(viewer.readNativeQualificationCapture(binding.viewId))
        const view = activeViews.find(item => item.id === binding.viewId), mechanism = renderedMechanism(binding.viewId)
        if (!view || capture.status !== 'captured' || mechanism.status !== 'rendered' || producer !== nativeQualificationProducer
          || binding.sourceVideoId !== video?.id || binding.sourceSha256 !== reference?.data.source.sha256
          || binding.timeSeconds !== modelTime || binding.sourceDrawRevision !== sourceDrawRevision
          || binding.completedSceneDrawEpoch !== capture.completedDrawEpoch || binding.sourceDrawRevision !== capture.drawRevision
          || binding.modelSourceCommit !== machine?.provenance.sourceCommit || binding.modelRawSHA256 !== machine?.provenance.sourceSha256
          || binding.modelDeliverySHA256 !== machine?.provenance.observedSha256 || binding.modelDeliveryByteLength !== machine?.provenance.observedByteLength
          || binding.currentBuildClosureSHA256 !== request.context.codeClosureSHA256
          || !equalRecord(binding.input, serializeInput(view.input)) || !equalRecord(binding.rectSourcePixels, view.rectSourcePixels)
          || !equalRecord(binding.camera, view.camera) || binding.presentation !== (view.presentation ?? 'native')
          || !equalRecord(binding.composite, view.composite ?? { mode: 'opaque' })
          || !equalRecord(binding.compositeProvenance, view.compositeProvenance ?? null)
          || !equalRecord(binding.imagePlaneWarp, view.authoredImagePlaneWarp)
          || !equalRecord(binding.resolvedImagePlaneWarp, capture.resolvedImagePlaneWarp)
          || !equalRecord(binding.sourceLayout, capture.sourceLayout)
          || !equalRecord(binding.partOverrides, view.partOverrides ?? NO_PART_OVERRIDES)
          || !equalRecord(binding.partOverrides, 'partOverrides' in mechanism ? mechanism.partOverrides : NO_PART_OVERRIDES)
          || binding.sourceImage.pixelFormat !== 'bgr8' || binding.sourceImage.sourceSha256 !== binding.sourceSha256
          || binding.sourceImage.frameIndex !== binding.decodedFrameIndex
          || Math.abs((player?.getTime() ?? Infinity) - binding.decodedTimeSeconds) > 0.5) throw new Error('Native bytes have no closed current source/model/input/camera/layout/epoch binding.')
        return capture
      }
      nativeQualificationBusy = true
      try {
        const sceneCapture = validate()
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(binding.input)))
        const inputSHA256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
        if (inputSHA256 !== binding.inputSHA256) throw new Error('Native complete physical input hash differs.')
        validate()
        const endpoint = new URL(request.sinkEndpoint, location.href)
        if (endpoint.origin !== location.origin || !endpoint.pathname.startsWith('/__native-qualification/')) throw new Error('Native binary sink must be this owned verification server.')
        const sink: NativeQualificationByteSink = {
          async put(bytes, { retention }) {
            const hash = await crypto.subtle.digest('SHA-256', bytes as BufferSource)
            const sha256 = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('')
            const response = await fetch(new URL(sha256, endpoint), { method: 'POST', headers: { 'content-type': 'application/octet-stream', 'x-native-retention': retention }, body: bytes as BodyInit })
            if (!response.ok) throw new Error(`Native binary upload failed: HTTP ${response.status}`)
            const stored = await response.json() as { sha256: string; byteLength: number; retention: typeof retention }
            const priority = { transient: 0, static: 1, reference: 2, 'selected-case': 3 }
            if (stored.sha256 !== sha256 || stored.byteLength !== bytes.byteLength || !(stored.retention in priority) || priority[stored.retention] < priority[retention]) throw new Error('Native binary sink returned changed content identity.')
            return stored
          },
        }
        const receipt = await producer.captureView(binding, sink, { ...request.context, sceneCapture })
        validate()
        return receipt
      } finally { nativeQualificationBusy = false }
    },
    disableNativeQualification() {
      if (nativeQualificationBusy) throw new Error('Wait for the active native capture before disabling it.')
      viewer.setNativeQualificationCaptureMode('disabled')
      nativeQualificationProducer?.dispose()
      nativeQualificationProducer = null
      nativeQualificationMachine = null
      nativeFeatureMarkers = []
      diagnosticReference = null
      configureLandmarkProbe()
    },
    renderedMechanism,
    assertSourceCompositeWeights,
    followVideo() {
      if (player) renderSource(player.getTime())
      if (referenceState === 'unavailable') return
      if (player?.getState() !== 'playing' && player?.getState() !== 'buffering') explore()
      else following()
    },
    async selectVideo(selector: string) {
      const next = resolveVideo(`?video=${encodeURIComponent(selector)}`)
      const route = new URL(location.href)
      route.searchParams.set('video', next.slug)
      history.pushState(null, '', route)
      await selectVideo(next)
      if (!player) throw new Error('The selected native YouTube player is unavailable.')
      return this.snapshot()
    },
  }
  Object.defineProperty(window, 'harmonicAnalyzer', { value: bridge, configurable: true })
}

viewer.resize()
selectRoute()
void fetchMachine()
requestAnimationFrame(tick)
