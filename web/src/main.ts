import { assertSourceCompositeWeights, beginNativeDiagnosticViewerLease, captureSourceLayout, createViewer, EXPLORING_VIEW_ID, loadMachine, ViewCapacityError, type CameraRecord, type CapturedSourceLayoutEntry, type LandmarkAnchor, type Machine, type NativeStagePointMapping, type NativeTargetShaderMeasurementRequest, type NativeTargetShaderReadback, type NativeTargetSurfaceReadback, type PartOverrideProvider, type SourceLayoutEntry, type SourceView, type Viewer } from './scene'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_MAX, physicalChannelAngle, squareWave } from './kinematics'
import { VIDEOS, resolveVideo, type Video } from './video-catalog'
import { createVideoPlayer, type PlaybackState, type VideoPlayer } from './youtube-player'
import { loadReference, serializeInput, SOURCE_STAGE_PERCENTAGES, LANDMARK_LIMIT_PX, type PlaybackView, type ReferenceState, type SourceSample } from './timeline'
import type { CompactVideoReference, DiagnosticSourcePublicationState } from './source-track'
import { createSourceVideoPlayer } from './source-player'
import { INPUT_FIELDS, equalRecord, type InputField } from './source-witness'
import { unavailableNativePrimitiveSnapshot, type NativeInputSnapshot, type NativePrimitiveSnapshot, type NativePrimitiveSubmissionMetadata, type NativeTargetSurfaceRequest } from './native-primitive-snapshot'
import { compileSourceAssemblyState, createSourceAssemblyBuffer, OPERATING_SOURCE_ASSEMBLY, solveSourceAssembly, type CompiledSourceAssembly, type SourceAssemblyBuffer, type SourceAssemblyState } from './source-assembly'

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
let currentAssembly = OPERATING_SOURCE_ASSEMBLY
let solvingAssembly = OPERATING_SOURCE_ASSEMBLY
let assemblyBuffer: SourceAssemblyBuffer | undefined
const assemblyOverrides: PartOverrideProvider = baseline => {
  assemblyBuffer ??= createSourceAssemblyBuffer()
  return solveSourceAssembly(solvingAssembly, baseline, assemblyBuffer)
}
let machine: Machine | null = null
let reference: CompactVideoReference | null = null
let player: VideoPlayer | null = null
let video: Video | null = null
let selectionAbort: AbortController | null = null
let playbackState: PlaybackState = 'unstarted'
let mode: 'following-video' | 'exploring' | 'reference-review' = 'exploring'
let referenceSeek: 'idle' | 'seeking' = 'idle'
let referenceState: ReferenceState = 'unavailable'
let modelState: 'loading' | 'ready' | 'unavailable' = 'loading'
let nativeDiagnosticLeaseActive = false
let nativeDiagnosticRefusal: string | null = null
function invalidateNativeDiagnosticLease(reason: string): void {
  if (nativeDiagnosticLeaseActive) nativeDiagnosticRefusal ??= reason
}
interface NativeDiagnosticRestoration {
  status: 'restored' | 'superseded' | 'failed'
  sourceProof: false
  sourceAcceptance: false
  inputRestored: boolean
  cameraRestored: boolean
  assemblyRestored: boolean
  layoutRestored: boolean
  paintRevision: 'clean' | 'pending'
  refusalReason: string | null
}
let lastNativeDiagnosticRestoration: NativeDiagnosticRestoration | null = null
interface NativeDiagnosticPublicationSnapshot {
  sourceProof: false
  sourceAcceptance: false
  prepareCount: number
  commitCount: number
  publishedBank: 0 | 1
  publishedSample: SourceSample
  activeViews: readonly PlaybackView[]
  referenceState: ReferenceState
  modelTime: number
  sourceDrawRevision: number
  paintRevision: 'clean' | 'pending'
  externalInput: NativeInputSnapshot
}
interface NativeDiagnosticPublication {
  readonly implementation: { renderSourceText: string; prepareAtText: string; commitPreparedText: string }
  renderSource(timeSeconds: number): void
  snapshot(): NativeDiagnosticPublicationSnapshot
}
interface NativeDiagnosticContext {
  readonly viewer: Viewer
  readonly machine: Machine
  readonly input: MechanismInput
  readonly provenance: Machine['provenance']
  readonly metadata: { sourceProof: false; sourceAcceptance: false; method: 'current-native-scoped-diagnostic-lease' }
  snapshot(): unknown
  nativePrimitiveSnapshot(): NativePrimitiveSnapshot
  readNativeDrawMetadata(): NativePrimitiveSubmissionMetadata
  readNativeTargetSurfaceAssociation(request: NativeTargetSurfaceRequest): NativeTargetSurfaceReadback
  readRegisteredNativeLandmarkAnchors(): readonly LandmarkAnchor[]
  resolveNativeStagePixelFromSourcePixel(viewId: string, sourcePixels: readonly [number, number]): NativeStagePointMapping
  measureNativeTargetShaderFeedback(request: NativeTargetShaderMeasurementRequest): NativeTargetShaderReadback
  withPublicationSamples<T>(samples: readonly SourceSample[], anchors: readonly LandmarkAnchor[], run: (transaction: NativeDiagnosticPublication) => T | Promise<T>): Promise<T>
}
let modelTime = 0
let manualMotion: 'idle' | 'turning' = 'idle'
let manualRevision: 'pending' | 'clean' = 'pending'
let paintRevision: 'pending' | 'clean' = 'pending'
let physicsState: 'available' | 'unavailable' = 'unavailable'
let playerSize: 'expanded' | 'compact' = 'expanded'
let activeViews: readonly PlaybackView[] = []
let initialCamera: CameraRecord | null = null
let explorationOrigin: 'interactive-default' | 'chosen-feasible-reconstruction' = 'interactive-default'
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
  sourceAssembly: SourceAssemblyState
  sourceLayout: readonly SourceLayoutEntry[]
  channelAnglesRad: Float64Array
  platenTravelM: number
  penTravelM: number
  effectiveBankDriveTurns: number
}
const mechanismDraws = new Map<string, MechanismDraw>()
let sourceDrawTimeSeconds = 0
let sourceDrawRevision = 0
let sourceDrawLayout: readonly SourceLayoutEntry[] = []
let diagnosticReference: CompactVideoReference | null = null
let diagnosticMachine: Machine | null = null
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
  if (nativeDiagnosticLeaseActive) return
  const enabled = verificationEnabled && mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused'
    && reference !== null && machine?.availability === 'available'
  if (enabled ? diagnosticReference === reference && diagnosticMachine === machine : diagnosticReference === null && diagnosticMachine === null) return
  viewer.setLandmarkProbe(null)
  viewer.setPartVisibilityProbe(null)
  diagnosticReference = null
  diagnosticMachine = null
  if (!enabled || !reference || machine?.availability !== 'available') return
  diagnosticReference = reference
  diagnosticMachine = machine
  viewer.setLandmarkProbe(machine.createLandmarkProbe(reference.data.anchors))
}

function renderPending(): void {
  if (paintRevision === 'clean') return
  paintRevision = 'clean'
  if (mode !== 'exploring' && referenceState === 'no-machine') drawSourceViews([], modelTime)
  else viewer.render(currentAssembly.state)
}


function updateMachine(source: MechanismInput, assembly: CompiledSourceAssembly = currentAssembly): void {
  if (machine?.availability !== 'available') return
  physicsState = 'unavailable'
  // The provider reads this update's fresh normal solve, never the previous
  // source view's detached transforms. Operating uses the full normal reset.
  solvingAssembly = assembly
  machine.update(source, assembly.state.kind === 'operating' ? undefined : assemblyOverrides)
  currentAssembly = assembly
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

function currentInputMeaning(drawViewId?: string) {
  if (mode === 'exploring') return 'manual-physical-input'
  if (!primaryView() || drawViewId === EXPLORING_VIEW_ID) return 'unverified-retained-physical-input'
  return 'chosen-feasible-approximation'
}

function lastContributingView(): PlaybackView | undefined {
  for (let i = activeViews.length - 1; i >= 0; i--) {
    const view = activeViews[i]!
    if (view.composite?.mode !== 'crossfade' || view.composite.opacity > 0) return view
  }
  return undefined
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
    if (!Object.hasOwn(view, 'authoredImagePlaneWarp') || !Object.hasOwn(view, 'sourceLayout')
      || view.authoredImagePlaneWarp === undefined || !Array.isArray(view.sourceLayout)
      || view.sourceLayout.length !== views.length
      || (view.authoredImagePlaneWarp !== null) !== (view.imagePlaneWarp !== undefined)) throw new Error(`Source view ${view.id} lacks explicit image-plane/layout metadata.`)
    for (let index = 0; index < views.length; index++) {
      const actual = views[index]!
      const entry = view.sourceLayout[index]!
      if (!entry || Object.keys(entry).length !== 5 || entry.viewId !== actual.id
        || !equalRecord(entry.rectSourcePixels, actual.rectSourcePixels)
        || entry.presentation !== actual.presentation || !equalRecord(entry.composite, actual.composite)
        || !Object.hasOwn(entry, 'resolvedImagePlaneWarp')
        || !equalRecord(entry.resolvedImagePlaneWarp, actual.imagePlaneWarp ?? null)) throw new Error(`Source view ${view.id} has stale or incomplete ordered source support.`)
    }
  }
}

function explore(): void {
  const chosen = primaryView()
  if (chosen && machine?.availability === 'available') {
    copyInput(chosen.input)
    updateMachine(input, compileSourceAssemblyState(chosen.sourceAssembly))
    viewer.applyCamera(chosen.camera)
    explorationOrigin = 'chosen-feasible-reconstruction'
  } else if (machine?.availability === 'available') updateMachine(input, OPERATING_SOURCE_ASSEMBLY)
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

function applyView(view: PlaybackView): void {
  if (!machine || machine.availability !== 'available') return
  updateMachine(view.input, compileSourceAssemblyState(view.sourceAssembly))
  let draw = mechanismDraws.get(view.id)
  if (!draw) {
    draw = { status: 'solved-for-draw', viewId: view.id, timeSeconds: sourceDrawTimeSeconds, sourceDrawRevision,
      input: createMechanismInput(), mechanicalProvenance: view.mechanicalProvenance, unobservedInputFields: view.unobservedInputFields, nativeGeometryAssumptions: view.nativeGeometryAssumptions,
      imagePlaneWarp: view.authoredImagePlaneWarp, resolvedImagePlaneWarp: view.imagePlaneWarp ?? null, sourceAssembly: currentAssembly.state, sourceLayout: sourceDrawLayout,
      channelAnglesRad: new Float64Array(20), platenTravelM: 0, penTravelM: 0, effectiveBankDriveTurns: 0 }
    mechanismDraws.set(view.id, draw)
  }
  draw.status = 'solved-for-draw'
  draw.timeSeconds = sourceDrawTimeSeconds
  draw.sourceDrawRevision = sourceDrawRevision
  copyInput(machine.input, draw.input)
  draw.mechanicalProvenance = view.mechanicalProvenance
  draw.unobservedInputFields = view.unobservedInputFields
  draw.nativeGeometryAssumptions = view.nativeGeometryAssumptions
  draw.imagePlaneWarp = view.authoredImagePlaneWarp
  draw.resolvedImagePlaneWarp = view.imagePlaneWarp ?? null
  draw.sourceAssembly = currentAssembly.state
  draw.sourceLayout = sourceDrawLayout
  draw.channelAnglesRad.set(machine.pose.channelAnglesRad)
  draw.platenTravelM = machine.pose.platenTravelM
  draw.penTravelM = machine.pose.magnifier.penTravelM
  draw.effectiveBankDriveTurns = (machine.pose.channelAnglesRad[19]! - machine.input.phases[19]!) / physicalChannelAngle(1, 19)
}

function drawSourceViews(views: readonly PlaybackView[], timeSeconds: number): void {
  sourceDrawTimeSeconds = timeSeconds
  sourceDrawRevision++
  sourceDrawLayout = verificationEnabled ? captureSourceLayout(views) : views[0]?.sourceLayout ?? []
  viewer.renderViews(views, beforeView, timeSeconds)
  for (const view of views) {
    const draw = mechanismDraws.get(view.id)
    if (draw?.sourceDrawRevision === sourceDrawRevision) draw.status = 'rendered'
  }
}

function renderedMechanism(viewId: string) {
  const draw = mechanismDraws.get(viewId)
  if (!draw) return { status: 'unavailable' as const, viewId, imagePlaneWarp: null, resolvedImagePlaneWarp: null, sourceAssembly: null, sourceLayout: [] }
  return {
    status: mode === 'exploring' || referenceState === 'unavailable' || draw.timeSeconds !== modelTime ? 'stale' as const : draw.status,
    viewId, timeSeconds: draw.timeSeconds, sourceDrawRevision: draw.sourceDrawRevision,
    method: 'actual-native-mechanism-solve' as const, input: serializeInput(draw.input),
    mechanicalProvenance: draw.mechanicalProvenance, unobservedInputFields: draw.unobservedInputFields,
    nativeGeometryAssumptions: draw.nativeGeometryAssumptions,
    imagePlaneWarp: draw.imagePlaneWarp, resolvedImagePlaneWarp: draw.resolvedImagePlaneWarp, sourceAssembly: draw.sourceAssembly, sourceLayout: draw.sourceLayout,
    channelAnglesRad: Array.from(draw.channelAnglesRad), platenTravelM: draw.platenTravelM, penTravelM: draw.penTravelM, effectiveBankDriveTurns: draw.effectiveBankDriveTurns,
  }
}

function sourceCapture<T extends {
  status: string
  viewId: string
  timeSeconds: number | null
  resolvedImagePlaneWarp: NonNullable<PlaybackView['imagePlaneWarp']> | null
  sourceAssembly: SourceAssemblyState | null
  sourceLayout: readonly CapturedSourceLayoutEntry[]
}>(capture: T) {
  const draw = mechanismDraws.get(capture.viewId)
  const bound = draw?.status === 'rendered' && draw.timeSeconds === capture.timeSeconds
    && equalRecord(draw.resolvedImagePlaneWarp, capture.resolvedImagePlaneWarp)
    && equalRecord(draw.sourceAssembly, capture.sourceAssembly)
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
    if (currentAssembly.state.kind !== 'operating') updateMachine(input, OPERATING_SOURCE_ASSEMBLY)
    drawSourceViews(sample.views, timeSeconds)
    paintRevision = 'clean'
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

function beforeView(_view: SourceView, index: number): void {
  const sample = activeViews[index]
  if (sample) applyView(sample)
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
  const forceView = mode === 'exploring' ? undefined : lastContributingView()
  const forceProvenance = mode === 'exploring' ? 'Manual physical calculation — not source measurements' : forceView ? 'Chosen-input physical calculation — not source measurements' : 'Last physical calculation — source reconstruction unavailable, not source-measured'
  const counterChoice = forceView?.unobservedInputFields.includes('setup.counterHeightM') ? `\nCounter ${forceView.input.setup.counterHeightM === null ? 'auto-level algorithm' : 'height'} chosen, not measured` : ''
  forceReadout.value = `${forceProvenance}${forceView ? ` · view ${forceView.id}` : ''}\n20 springs · ${minimum.toFixed(2)}–${maximum.toFixed(2)} N\nTorque residual ${machine.pose.equilibriumResidualNm.toExponential(1)} N·m\nPaper feed ${(machine.pose.platenTravelM * 1000).toFixed(2)} mm${counterChoice}`
}

function editMechanism(action: () => void): void {
  if (mode !== 'exploring' || modelState !== 'ready') return
  invalidateNativeDiagnosticLease('Manual mechanism input changed')
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
  invalidateNativeDiagnosticLease('The selected native/source context changed')
  selectionAbort?.abort()
  const selection = new AbortController()
  selectionAbort = selection
  player?.destroy()
  player = null
  reference = null
  activeViews = []
  explorationOrigin = 'interactive-default'
  currentAssembly = OPERATING_SOURCE_ASSEMBLY
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
      if (playbackState !== state) invalidateNativeDiagnosticLease(`Source playback changed from ${playbackState} to ${state}`)
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
    machine = await loadMachine(viewer.scene, { nativePrimitiveSnapshots: verificationEnabled })
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
  if (nativeDiagnosticLeaseActive) return
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
      else if (viewer.controls.enableDamping || viewer.controls.autoRotate) viewer.controls.update()
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

const viewer = createViewer(canvas, () => { paintRevision = 'pending' }, verificationEnabled)
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
  invalidateNativeDiagnosticLease('Manual crank motion changed')
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
  invalidateNativeDiagnosticLease('Source-following was requested')
  try {
    renderSource(player.getTime())
    if (referenceState === 'unavailable') return
    if (player.getState() !== 'playing' && player.getState() !== 'buffering') explore()
    else following()
  } catch (error) { notice(physicsError, error instanceof Error ? error.message : String(error)) }
})
fitButton.addEventListener('click', () => {
  if (mode !== 'exploring') return
  invalidateNativeDiagnosticLease('Manual camera fitting was requested')
  viewer.fitView()
})
compactButton.addEventListener('click', () => {
  playerSize = playerSize === 'expanded' ? 'compact' : 'expanded'
  videoDock.dataset.size = playerSize
  workspace.dataset.playerSize = playerSize
  compactButton.textContent = playerSize === 'compact' ? 'Expand player' : 'Compact player'
  compactButton.setAttribute('aria-expanded', String(playerSize === 'expanded'))
  viewer.resize()
  paintRevision = 'pending'
  invalidateNativeDiagnosticLease('The player layout changed')
})
retryModel.addEventListener('click', () => { void fetchMachine() })
window.addEventListener('popstate', selectRoute)
for (const type of ['pointerdown', 'wheel'] as const) canvas.addEventListener(type, (event) => {
  if (event.isTrusted && mode === 'exploring') invalidateNativeDiagnosticLease('Manual camera interaction began')
})

if (verificationEnabled) {
  const bridge = {
    async withNativeDiagnosticLease<T>(run: (context: NativeDiagnosticContext) => T | Promise<T>): Promise<T> {
      if (nativeDiagnosticLeaseActive || typeof run !== 'function') throw new Error('A native diagnostic lease is already active or its callback is invalid')
      if (!machine || machine.availability !== 'available' || physicsState !== 'available' || manualRevision !== 'clean' || paintRevision !== 'clean'
        || referenceSeek !== 'idle' || player?.getState() === 'playing' || player?.getState() === 'buffering') throw new Error('Native diagnostics require a current completed idle native model/frame and paused source')
      const actualMachine = machine
      const actualReference = reference
      const actualPlayer = player
      const actualPlaybackState = actualPlayer?.getState()
      const actualSourceTime = actualPlayer?.getTime()
      const saved = {
        input: structuredClone(input), machineInput: structuredClone(actualMachine.input), camera: cameraRecord(), assembly: currentAssembly,
        views: activeViews, layout: captureSourceLayout(activeViews), mode, referenceState, modelTime, sourceDrawTimeSeconds, sourceDrawRevision, sourceDrawLayout,
        manualMotion, manualRevision, explorationOrigin, diagnosticReference, diagnosticMachine,
        draws: new Map([...mechanismDraws].map(([id, draw]) => [id, structuredClone(draw)])),
        controlsTarget: viewer.controls.target.clone(), controlsEnabled: viewer.controls.enabled,
        enableDamping: viewer.controls.enableDamping, autoRotate: viewer.controls.autoRotate,
        canvasStyle: canvas.style.cssText, pixelRatio: viewer.renderer.getPixelRatio(),
        sceneBackground: viewer.scene.background, sceneEnvironment: viewer.scene.environment,
        cameraUp: viewer.camera.up.clone(), cameraNear: viewer.camera.near, cameraFar: viewer.camera.far, cameraLayers: viewer.camera.layers.mask,
        cameraScale: viewer.camera.scale.clone(), cameraZoom: viewer.camera.zoom, cameraFocus: viewer.camera.focus,
        cameraFilmGauge: viewer.camera.filmGauge, cameraFilmOffset: viewer.camera.filmOffset, cameraAspect: viewer.camera.aspect,
        cameraView: viewer.camera.view ? { ...viewer.camera.view } : null,
      }
      const rendererMethods = ['render', 'clear', 'setRenderTarget', 'readRenderTargetPixels'] as const
      const originals = rendererMethods.map(key => ({ key, value: viewer.renderer[key] }))
      const gl = viewer.renderer.getContext()
      const glMethods = ['createFramebuffer', 'createTexture', 'createRenderbuffer'] as const
      const glOriginals = glMethods.map(key => ({ key, value: gl[key] }))
      const viewerLease = beginNativeDiagnosticViewerLease(viewer)
      nativeDiagnosticLeaseActive = true
      nativeDiagnosticRefusal = null
      lastNativeDiagnosticRestoration = null
      let publicationActive = false
      let contextLive = true
      const ownsSourceState = () => {
        if (machine !== actualMachine || reference !== actualReference || player !== actualPlayer) {
          nativeDiagnosticRefusal ??= 'The selected native/source context changed'
        } else if (actualPlayer?.getState() !== actualPlaybackState || actualPlayer?.getTime() !== actualSourceTime) {
          nativeDiagnosticRefusal ??= 'The actual source playback state or clock changed'
        }
        return nativeDiagnosticRefusal === null
      }
      const throwCleanupFailures = (errors: unknown[], failed: boolean, original: unknown) => {
        if (!errors.length) return
        if (failed) throw new AggregateError([original, ...errors], 'Native diagnostic callback and cleanup both failed', { cause: original })
        if (errors.length === 1) throw errors[0]
        throw new AggregateError(errors, 'Native diagnostic cleanup failed')
      }
      let callbackFailed = false
      let callbackError: unknown
      const requireLease = () => {
        if (!contextLive || !nativeDiagnosticLeaseActive) throw new Error('The native diagnostic lease expired')
        if (!ownsSourceState()) throw new Error(`The native diagnostic lease was superseded: ${nativeDiagnosticRefusal}`)
      }
      try {
        const result = await run({
          viewer, machine: actualMachine, input, provenance: actualMachine.provenance,
          metadata: { sourceProof: false, sourceAcceptance: false, method: 'current-native-scoped-diagnostic-lease' },
          snapshot() { requireLease(); return { ...bridge.snapshot(), sourceProof: false, sourceAcceptance: false } },
          nativePrimitiveSnapshot() { requireLease(); return unavailableNativePrimitiveSnapshot('Native capture is suspended during diagnostic-only rendering', 'stale') },
          readNativeDrawMetadata() { requireLease(); return viewerLease.readNativeDrawMetadata() },
          readNativeTargetSurfaceAssociation(request) { requireLease(); return viewerLease.readNativeTargetSurfaceAssociation(request) },
          readRegisteredNativeLandmarkAnchors() { requireLease(); return viewerLease.readRegisteredNativeLandmarkAnchors() },
          resolveNativeStagePixelFromSourcePixel(viewId, sourcePixels) { requireLease(); return viewerLease.resolveNativeStagePixelFromSourcePixel(viewId, sourcePixels) },
          measureNativeTargetShaderFeedback(request) { requireLease(); return viewerLease.measureNativeTargetShaderFeedback(request) },
          async withPublicationSamples(samples, anchors, callback) {
            requireLease()
            if (!actualReference || publicationActive || typeof callback !== 'function') throw new Error('Diagnostic publication requires the same loaded source reference and a single callback')
            publicationActive = true
            const publicationState = { mode, referenceState, activeViews, modelTime, sourceDrawRevision, sourceDrawTimeSeconds, sourceDrawLayout,
              input: structuredClone(input), machineInput: structuredClone(actualMachine.input), assembly: currentAssembly, camera: cameraRecord() }
            let publicationFailed = false
            let publicationError: unknown
            try {
              viewer.setLandmarkProbe(actualMachine.createLandmarkProbe(anchors))
              return await actualReference.withDiagnosticSamples(samples, (state: DiagnosticSourcePublicationState) => {
                let active = true
                const requireTransaction = () => { requireLease(); if (!active) throw new Error('The diagnostic publication transaction has expired') }
                const transaction: NativeDiagnosticPublication = {
                  implementation: { renderSourceText: renderSource.toString(), prepareAtText: state.prepareAtImplementation, commitPreparedText: state.commitPreparedImplementation },
                  renderSource(timeSeconds) { requireTransaction(); renderSource(timeSeconds) },
                  snapshot() {
                    requireTransaction()
                    return { ...state.snapshot(), sourceProof: false, sourceAcceptance: false, activeViews: structuredClone(activeViews),
                      referenceState, modelTime, sourceDrawRevision, paintRevision, externalInput: structuredClone(serializeInput(input)) }
                  },
                }
                return Promise.resolve(callback(transaction)).then((value) => {
                  requireTransaction()
                  return value
                }).finally(() => { active = false })
              })
            } catch (error) {
              publicationFailed = true
              publicationError = error
              throw error
            } finally {
              const errors: unknown[] = []
              try {
                // A newer playback/route/manual owner must never receive this
                // transaction's former source state, even before outer cleanup.
                if (contextLive && nativeDiagnosticLeaseActive && ownsSourceState()) {
                  mode = publicationState.mode
                  referenceState = publicationState.referenceState
                  activeViews = publicationState.activeViews
                  modelTime = publicationState.modelTime
                  sourceDrawRevision = publicationState.sourceDrawRevision
                  sourceDrawTimeSeconds = publicationState.sourceDrawTimeSeconds
                  sourceDrawLayout = publicationState.sourceDrawLayout
                  copyInput(publicationState.input)
                  updateMachine(publicationState.machineInput, publicationState.assembly)
                  viewer.applyCamera(publicationState.camera)
                }
              } catch (error) { errors.push(error) }
              finally { publicationActive = false }
              throwCleanupFailures(errors, publicationFailed, publicationError)
            }
          },
        })
        requireLease()
        return result
      } catch (error) {
        callbackFailed = true
        callbackError = error
        throw error
      } finally {
        contextLive = false
        const owned = ownsSourceState()
        const errors: unknown[] = []
        const restore = (action: () => void) => { try { action() } catch (error) { errors.push(error) } }
        const currentCamera = owned ? saved.camera : cameraRecord()
        const currentTarget = viewer.controls.target.clone()
        const currentControlsEnabled = viewer.controls.enabled
        let restored = false
        try {
          // Resource ownership is unconditional; source-state ownership is not.
          for (const { key, value } of originals) restore(() => { Object.defineProperty(viewer.renderer, key, { configurable: true, writable: true, value }) })
          for (const { key, value } of glOriginals) restore(() => { Object.defineProperty(gl, key, { configurable: true, writable: true, value }) })
          restore(() => { canvas.style.cssText = saved.canvasStyle })
          restore(() => { viewer.renderer.setPixelRatio(saved.pixelRatio); viewer.resize() })
          viewer.scene.background = saved.sceneBackground
          viewer.scene.environment = saved.sceneEnvironment
          restore(() => { viewerLease.restoreProbes() })
          if (owned) restore(() => {
            mode = saved.mode
            referenceState = saved.referenceState
            activeViews = saved.views
            modelTime = saved.modelTime
            manualMotion = saved.manualMotion
            explorationOrigin = saved.explorationOrigin
            diagnosticReference = saved.diagnosticReference
            diagnosticMachine = saved.diagnosticMachine
            copyInput(saved.input)
            updateMachine(saved.machineInput, saved.assembly)
          })
          restore(() => {
            viewer.camera.up.copy(saved.cameraUp)
            viewer.camera.near = saved.cameraNear
            viewer.camera.far = saved.cameraFar
            viewer.camera.layers.mask = saved.cameraLayers
            viewer.setInteraction(mode === 'exploring' ? 'exploring' : 'following-video')
            viewer.controls.target.copy(owned ? saved.controlsTarget : currentTarget)
            viewer.controls.enabled = owned ? saved.controlsEnabled : currentControlsEnabled
            viewer.controls.enableDamping = false
            viewer.controls.autoRotate = false
            viewer.applyCamera(currentCamera)
            // applyCamera rebases controls and normalizes an authored quaternion.
            // A restoration receipt instead owns exact already-solved camera bits.
            viewer.camera.position.fromArray(currentCamera.positionMetres)
            viewer.camera.quaternion.fromArray(currentCamera.quaternion)
            viewer.camera.up.copy(saved.cameraUp)
            viewer.camera.scale.copy(saved.cameraScale)
            viewer.camera.zoom = saved.cameraZoom
            viewer.camera.focus = saved.cameraFocus
            viewer.camera.filmGauge = saved.cameraFilmGauge
            viewer.camera.filmOffset = saved.cameraFilmOffset
            if (owned) viewer.camera.aspect = saved.cameraAspect
            viewer.camera.view = saved.cameraView ? { ...saved.cameraView } : null
            viewer.camera.updateProjectionMatrix()
            viewer.camera.updateMatrixWorld(true)
            viewer.controls.target.copy(owned ? saved.controlsTarget : currentTarget)
          })
          if (owned) restore(() => {
            if (saved.mode !== 'exploring' && saved.views.length) drawSourceViews(saved.views, saved.modelTime)
            else if (saved.mode !== 'exploring' && saved.referenceState === 'no-machine') viewer.renderViews([], undefined, saved.modelTime)
            else viewer.render(saved.assembly.state)
            sourceDrawRevision = saved.sourceDrawRevision
            sourceDrawTimeSeconds = saved.sourceDrawTimeSeconds
            sourceDrawLayout = saved.sourceDrawLayout
            mechanismDraws.clear()
            for (const [id, draw] of saved.draws) mechanismDraws.set(id, draw)
            manualRevision = saved.manualRevision
            paintRevision = 'clean'
            restored = true
          })
          else paintRevision = 'pending'
          viewer.controls.enableDamping = saved.enableDamping
          viewer.controls.autoRotate = saved.autoRotate
        } finally {
          restore(() => { viewerLease.release() })
          nativeDiagnosticLeaseActive = false
          lastTick = performance.now()
          if (!owned) restore(() => {
            // Source-track temporary banks have now unwound. Draw only the
            // latest real route/playback/manual state, never a saved exposure.
            configureLandmarkProbe()
            if (player && (player.getState() === 'playing' || player.getState() === 'buffering')) {
              renderSource(player.getTime())
              if (referenceState !== 'unavailable') following()
            } else if (mode === 'exploring') {
              updateMachine(input)
              manualRevision = 'clean'
              renderPending()
            } else if (activeViews.length) drawSourceViews(activeViews, modelTime)
            updateControlState()
            updateHud()
          })
          lastNativeDiagnosticRestoration = {
            status: errors.length ? 'failed' : restored ? 'restored' : 'superseded', sourceProof: false, sourceAcceptance: false,
            inputRestored: owned && equalRecord(serializeInput(input), serializeInput(saved.input)),
            cameraRestored: owned && equalRecord(cameraRecord(), saved.camera),
            assemblyRestored: owned && currentAssembly === saved.assembly,
            layoutRestored: owned && equalRecord(captureSourceLayout(activeViews), saved.layout), paintRevision,
            refusalReason: nativeDiagnosticRefusal,
          }
          throwCleanupFailures(errors, callbackFailed, callbackError)
        }
      }
    },
    snapshot() {
      const chosen = mode === 'exploring' ? undefined : primaryView()
      const sourceLayout = verificationEnabled ? captureSourceLayout(activeViews) : chosen?.sourceLayout ?? []
      return {
        videoId: video?.id ?? null, playerVideoId: player?.getVideoId() ?? null, mode, playerState: player?.getState() ?? playbackState,
        videoTime: player?.getTime() ?? null, modelTime, referenceState, modelState, missingBindings: machine?.missing ?? [],
        modelProvenance: machine?.provenance ?? null, camera: cameraRecord(), input: serializeInput(input),
        diagnosticLease: { active: nativeDiagnosticLeaseActive, restoration: lastNativeDiagnosticRestoration },
        sourceDrawRevision, sourceDrawTimeSeconds, diagnosticCapture: diagnosticReference !== null && diagnosticReference === reference && diagnosticMachine === machine && mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused' ? 'paused-reference-review' : 'disabled',
        sourceFollowing: reference ? { kind: reference.kind, stageLadder: SOURCE_STAGE_PERCENTAGES, finalTolerancePx: LANDMARK_LIMIT_PX, stages: reference.stageStatus, stageEvidence: 'unmeasured: no independently bound rendered report loaded', sourceMeasurements: reference.data.sourceMeasurements ?? null } : null,
        imagePlaneWarp: chosen ? chosen.authoredImagePlaneWarp : null,
        resolvedImagePlaneWarp: chosen?.imagePlaneWarp ?? null,
        sourceAssembly: physicsState === 'available' ? currentAssembly.state : null, sourceLayout,
        mechanicalProvenance: mode === 'exploring' ? null : primaryView()?.mechanicalProvenance ?? null,
        unobservedInputFields: mode === 'exploring' ? INPUT_FIELDS : primaryView()?.unobservedInputFields ?? INPUT_FIELDS,
        explorationOrigin, inputMeaning: currentInputMeaning(),
        nativeGeometryAssumptions: reference?.data.nativeGeometryAssumptions ?? [],
        physics: machine && physicsState === 'available' ? { renderedViewId: mode === 'exploring' ? EXPLORING_VIEW_ID : lastContributingView()?.id ?? null, mechanicalProvenance: mode === 'exploring' ? null : lastContributingView()?.mechanicalProvenance ?? null, springForcesN: Array.from(machine.pose.springForcesN), springLengthsM: Array.from(machine.pose.springLengthsM), equilibriumResidualNm: machine.pose.equilibriumResidualNm, platenTravelM: machine.pose.platenTravelM, summingAngleRad: machine.pose.summingAngleRad } : null,
        playerAudio: player?.getAudio() ?? null,
        views: activeViews.map((view) => ({ id: view.id, rectSourcePixels: view.rectSourcePixels, presentation: view.presentation, composite: view.composite, imagePlaneWarp: view.authoredImagePlaneWarp, resolvedImagePlaneWarp: view.imagePlaneWarp ?? null, sourceAssembly: view.sourceAssembly ?? OPERATING_SOURCE_ASSEMBLY.state, sourceLayout: verificationEnabled ? sourceLayout : view.sourceLayout, camera: view.camera, input: serializeInput(view.input), mechanicalProvenance: view.mechanicalProvenance, unobservedInputFields: view.unobservedInputFields, sourceSampling: view.sourceSampling, nativeGeometryAssumptions: view.nativeGeometryAssumptions, renderedMechanism: renderedMechanism(view.id) })),
      }
    },
    nativePrimitiveSnapshot(viewId?: string) {
      // Capture the real manual frame even when every source packet is unavailable.
      // Never solve a pose, select an old camera or request another native draw here.
      let capture: NativePrimitiveSnapshot
      if (nativeDiagnosticLeaseActive) capture = unavailableNativePrimitiveSnapshot('Native capture is suspended during diagnostic-only rendering', 'stale')
      else if (!machine || modelState !== 'ready') capture = unavailableNativePrimitiveSnapshot(`Native model ${modelState}: ${machine?.loadError ?? 'no loaded Machine'}`)
      else if (physicsState !== 'available') capture = unavailableNativePrimitiveSnapshot('The current native mechanical update is unverified')
      else if (manualRevision !== 'clean' || paintRevision !== 'clean' || referenceSeek !== 'idle') capture = unavailableNativePrimitiveSnapshot('The current input, paint or source seek has not completed its native draw', 'stale')
      else capture = machine.nativePrimitiveSnapshot(viewer, viewId)
      const draw = capture.status === 'captured' ? capture.manifest.draw : null
      const sourceBound = draw !== null && mode !== 'exploring' && primaryView() !== undefined
        && draw.viewId !== EXPLORING_VIEW_ID && referenceState !== 'unavailable' && draw.timeSeconds === modelTime
        && activeViews.some(view => view.id === draw.viewId && (view.composite?.mode !== 'crossfade' || view.composite.opacity > 0)
          && equalRecord(view.sourceAssembly ?? OPERATING_SOURCE_ASSEMBLY.state, draw.sourceAssembly))
      return { ...capture, context: {
        videoId: video?.id ?? null, playerVideoId: player?.getVideoId() ?? null, mode,
        playerState: player?.getState() ?? playbackState, videoTimeSeconds: player?.getTime() ?? null,
        modelTimeSeconds: modelTime, sourceDrawRevision, sourceDrawTimeSeconds, referenceState,
        inputMeaning: currentInputMeaning(draw?.viewId),
        sourceFollowing: mode === 'exploring' ? 'disabled-manual-mode' : sourceBound ? 'chosen-feasible-not-source-qualified' : 'unavailable',
        nativeDrawViewId: draw?.viewId ?? null, nativeGeometryIssues: capture.manifest?.issues ?? null,
        sourceAssembly: draw?.sourceAssembly ?? null,
        manualMotion, referenceSeek, physicsState, modelState,
      } }
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
      invalidateNativeDiagnosticLease('A native reference review was requested')
      const prepared = reference.prepareAt(timeSeconds)
      validateSourceViews(prepared.views)
      viewer.preflightViews(prepared.views)
      copyInput(input, reviewRollbackInput)
      const previousAssembly = currentAssembly
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
          updateMachine(input, previousAssembly)
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
      invalidateNativeDiagnosticLease('Manual exploration was requested')
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
    renderedMechanism,
    assertSourceCompositeWeights,
    followVideo() {
      invalidateNativeDiagnosticLease('Source-following was requested')
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
