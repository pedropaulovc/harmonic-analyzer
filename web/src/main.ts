import { assertSourceCompositeWeights, beginNativeDiagnosticViewerLease, captureSourceLayout, createViewer, EXPLORING_VIEW_ID, loadMachine, ViewCapacityError, type CameraRecord, type CapturedSourceLayoutEntry, type LandmarkAnchor, type Machine, type NativeStagePointMapping, type NativeTargetShaderMeasurementRequest, type NativeTargetShaderReadback, type NativeTargetSurfaceReadback, type PartOverrideProvider, type SourceLayoutEntry, type SourceView, type Viewer } from './scene'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_MAX, physicalChannelAngle, squareWave } from './kinematics'
import { VIDEOS, resolveVideo, type Video } from './video-catalog'
import { createVideoPlayer, type PlaybackState, type VideoPlayer } from './youtube-player'
import { loadReference, serializeInput, SOURCE_STAGE_PERCENTAGES, LANDMARK_LIMIT_PX, type PlaybackView, type ReferenceState, type SourceSample } from './timeline'
import type { CompactVideoReference, DiagnosticSourcePublicationState, SourcePublicationReference } from './source-track'
import { buildOriginalPresentationSamples, createSourceVideoPlayer, isSourceVideoPlayer } from './source-player'
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
const sourceControls = element('#source-controls')
const sourcePlay = element<HTMLButtonElement>('#source-play')
const sourceMute = element<HTMLButtonElement>('#source-mute')
const sourceVolume = element<HTMLInputElement>('#source-volume')
const sourceScrub = element<HTMLInputElement>('#source-scrub')
const sourceScrubTime = element<HTMLOutputElement>('#source-scrub-time')
const sourceSeekStatus = element('#source-seek-status')
const sourceSeekTime = element<HTMLInputElement>('#source-seek-time')
const sourceSeekButton = element<HTMLButtonElement>('#source-seek')
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
let presentedSampleTimes = new Map<number, number>()
let player: VideoPlayer | null = null
let video: Video | null = null
let selectionAbort: AbortController | null = null
let playbackState: PlaybackState = 'unstarted'
let mode: 'following-video' | 'exploring' | 'reference-review' = 'exploring'
let referenceSeek: 'idle' | 'seeking' | 'preroll' = 'idle'
let manualSourceSeek: 'idle' | 'seeking' = 'idle'
let referenceState: ReferenceState = 'unavailable'
let modelState: 'loading' | 'ready' | 'unavailable' = 'loading'
let nativeDiagnosticLeaseActive = false
let nativeDiagnosticRefusal: string | null = null
let resumeNativeDiagnosticSource: (() => void) | null = null
function invalidateNativeDiagnosticLease(reason: string): void {
  if (!nativeDiagnosticLeaseActive || nativeDiagnosticRefusal !== null) return
  nativeDiagnosticRefusal = reason
  resumeNativeDiagnosticSource?.()
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
  sourceSampleTimeSeconds: number
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
// Authored selection key, never a replacement for real native/model/draw clocks.
let sourceSampleTimeSeconds = 0
let manualMotion: 'idle' | 'turning' = 'idle'
let manualSceneOwnership: 'initial' | 'owned' = 'initial'
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
  effectiveSourceOverridePartPaths: string[]
  sourceLayout: readonly SourceLayoutEntry[]
  channelAnglesRad: Float64Array
  platenTravelM: number
  penTravelM: number
  effectiveBankDriveTurns: number
}

interface NativeDiagnosticFrame {
  input: MechanismInput
  machineInput: MechanismInput
  camera: CameraRecord
  assembly: CompiledSourceAssembly
  views: readonly PlaybackView[]
  layout: readonly CapturedSourceLayoutEntry[]
  mode: 'following-video' | 'exploring' | 'reference-review'
  referenceState: ReferenceState
  modelTime: number
  sourceSampleTimeSeconds: number
  sourceDrawTimeSeconds: number
  sourceDrawRevision: number
  sourceDrawLayout: readonly SourceLayoutEntry[]
  manualMotion: 'idle' | 'turning'
  manualSceneOwnership: 'initial' | 'owned'
  manualRevision: 'pending' | 'clean'
  explorationOrigin: 'interactive-default' | 'chosen-feasible-reconstruction'
  diagnosticReference: CompactVideoReference | null
  diagnosticMachine: Machine | null
  physicsState: 'available' | 'unavailable'
  sourceNotice: string
  physicsNotice: string
  draws: Map<string, MechanismDraw>
  controlsTarget: Viewer['controls']['target']
  controlsEnabled: boolean
  enableDamping: boolean
  autoRotate: boolean
  cameraUp: Viewer['camera']['up']
  cameraNear: number
  cameraFar: number
  cameraLayers: number
  cameraScale: Viewer['camera']['scale']
  cameraZoom: number
  cameraFocus: number
  cameraFilmGauge: number
  cameraFilmOffset: number
  cameraAspect: number
  cameraView: Viewer['camera']['view']
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
  if (nativeDiagnosticLeaseActive && nativeDiagnosticRefusal === null) return
  const enabled = verificationEnabled && mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused'
    && referenceState === 'approximate' && reference !== null && machine?.availability === 'available'
  if (enabled ? diagnosticReference === reference && diagnosticMachine === machine : diagnosticReference === null && diagnosticMachine === null) return
  viewer.setLandmarkProbe(null)
  viewer.setPartVisibilityProbe(null)
  diagnosticReference = null
  diagnosticMachine = null
  if (!enabled || !reference || machine?.availability !== 'available') return
  diagnosticReference = reference
  diagnosticMachine = machine
  viewer.setLandmarkProbe(machine.createLandmarkProbe(reference.landmarkProbeAnchors))
}

function renderPending(): void {
  if (paintRevision === 'clean') return
  paintRevision = 'clean'
  if (mode !== 'exploring' && referenceState === 'hold-last-readable' && activeViews.length) drawSourceViews(activeViews, modelTime)
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
  if (mode === 'reference-review' && referenceSeek !== 'idle') return 'retained-displayed-input-during-original-seek-not-current-source-match'
  if (mode === 'exploring') return 'manual-physical-input'
  if (referenceState === 'hold-last-readable') return 'held-readable-approximation-not-current-source-match'
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
  followButton.disabled = modelState !== 'ready' || !reference || referenceSeek !== 'idle' || manualSourceSeek !== 'idle'
  pauseButton.disabled = !player
  pauseButton.textContent = playbackState === 'playing' || playbackState === 'buffering' ? 'Pause & explore' : 'Play video'
  const local = player && isSourceVideoPlayer(player) ? player : null
  sourceControls.hidden = local === null
  sourcePlay.disabled = !local
  sourcePlay.textContent = pauseButton.textContent
  sourceScrub.disabled = !local || mode !== 'exploring' || !['paused', 'ended'].includes(local.getState()) || manualSourceSeek !== 'idle' || referenceSeek !== 'idle'
  sourceSeekTime.disabled = sourceScrub.disabled
  sourceSeekButton.disabled = sourceScrub.disabled
  if (local) {
    sourceScrub.max = String(videoContainer.querySelector('video')?.duration ?? 1)
    sourceSeekTime.max = sourceScrub.max
    sourceVolume.value = String(local.getAudio().volume)
    sourceMute.setAttribute('aria-pressed', String(local.getMuted()))
    sourceMute.textContent = local.getMuted() ? 'Unmute' : 'Mute'
  }
}

async function seekOriginalManually(timeSeconds: number) {
  invalidateNativeDiagnosticLease('A manual original source seek was requested')
  const nativePlayer = player
  if (!nativePlayer || !isSourceVideoPlayer(nativePlayer)) throw new Error('Safe original-byte manual seeking requires the local original source adapter.')
  if (mode !== 'exploring' || !['paused', 'ended'].includes(nativePlayer.getState())) throw new Error('Pause in manual exploration before seeking the original source.')
  if (manualSourceSeek !== 'idle') throw new Error('An original manual seek is already active.')
  manualSourceSeek = 'seeking'
  sourceControls.dataset.state = 'loading'
  sourceControls.setAttribute('aria-busy', 'true')
  sourceSeekStatus.textContent = 'Seeking original exposure from a verified IDR…'
  updateControlState()
  try {
    const presented = await nativePlayer.seek(timeSeconds, 'manual')
    if (player !== nativePlayer) throw new Error('The source changed during manual seeking.')
    sourceControls.dataset.state = 'success'
    sourceSeekStatus.textContent = `Paused original frame ${presented.frameIndex} · ${presented.mediaTime.toFixed(6)} s.`
    return presented
  } catch (error) {
    if (player === nativePlayer) {
      sourceControls.dataset.state = 'error'
      sourceSeekStatus.textContent = error instanceof Error ? error.message : String(error)
      notice(videoError, sourceSeekStatus.textContent)
    }
    throw error
  } finally {
    if (player === nativePlayer) {
      manualSourceSeek = 'idle'
      sourceControls.setAttribute('aria-busy', 'false')
      updateControlState()
    }
  }
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
  } else if (machine?.availability === 'available') updateMachine(input, currentAssembly)
  activeViews = []
  mode = 'exploring'
  manualSceneOwnership = 'owned'
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
      effectiveSourceOverridePartPaths: [], channelAnglesRad: new Float64Array(20), platenTravelM: 0, penTravelM: 0, effectiveBankDriveTurns: 0 }
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
  draw.effectiveSourceOverridePartPaths.length = 0
  if (currentAssembly.state.kind !== 'operating' && assemblyBuffer) for (const override of assemblyBuffer.overrides) draw.effectiveSourceOverridePartPaths.push(override.partPath)
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
  if (!draw) return { status: 'unavailable' as const, viewId, imagePlaneWarp: null, resolvedImagePlaneWarp: null, sourceAssembly: null, effectiveSourceOverridePartPaths: [], sourceLayout: [] }
  return {
    status: mode === 'exploring' || referenceState !== 'approximate' || draw.timeSeconds !== modelTime ? 'stale' as const : draw.status,
    viewId, timeSeconds: draw.timeSeconds, sourceDrawRevision: draw.sourceDrawRevision,
    method: 'actual-native-mechanism-solve' as const, input: serializeInput(draw.input),
    mechanicalProvenance: draw.mechanicalProvenance, unobservedInputFields: draw.unobservedInputFields,
    nativeGeometryAssumptions: draw.nativeGeometryAssumptions,
    imagePlaneWarp: draw.imagePlaneWarp, resolvedImagePlaneWarp: draw.resolvedImagePlaneWarp, sourceAssembly: draw.sourceAssembly, effectiveSourceOverridePartPaths: draw.effectiveSourceOverridePartPaths.slice(), sourceLayout: draw.sourceLayout,
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
      : capture.status === 'captured' && (!bound || referenceState !== 'approximate' || capture.timeSeconds !== modelTime) ? 'stale' as const : capture.status,
    imagePlaneWarp: bound ? draw.imagePlaneWarp : null,
  }
}


function renderSource(timeSeconds: number, sourceReference: SourcePublicationReference | null = reference, sourceExposureTimeSeconds = timeSeconds): void {
  configureLandmarkProbe()
  if (!sourceReference || !machine || machine.availability !== 'available') {
    referenceState = 'unavailable'
    renderPending()
    return
  }
  if (sourceReference === reference && player && isSourceVideoPlayer(player) && player.getSeekState() === 'idle') {
    const presented = player.getPresentation()
    if (!presented) {
      referenceState = 'unavailable'
      throw new Error('The original video has no current owned presented exposure. Complete a safe seek or real playback before restoring its pose.')
    }
    sourceExposureTimeSeconds = presentedSampleTimes.get(presented.frameIndex)
      ?? presented.pts * presented.timeBase[0] / presented.timeBase[1]
  }
  let prepared = sourceReference.prepareAt(sourceExposureTimeSeconds)
  if (prepared.state === 'hold-last-readable') {
    // Pooled publication banks are reused. Own the DISPLAYED readable views once
    // at hold entry, never adopt the excluded exposure's camera/input/assembly.
    let heldViews = activeViews.length && referenceState !== 'hold-last-readable' ? structuredClone(activeViews) : activeViews
    if (!heldViews.length && (mode !== 'exploring' || manualSceneOwnership === 'initial')) {
      const readable = sourceReference.prepareLastReadableAt(sourceExposureTimeSeconds) ?? sourceReference.prepareInitialReadable()
      if (readable) {
        validateSourceViews(readable.views)
        viewer.preflightViews(readable.views)
        const preceding = sourceReference.commitPrepared()
        heldViews = structuredClone(preceding.views)
        activeViews = heldViews
        const chosen = primaryView()
        if (chosen) copyInput(chosen.input)
        drawSourceViews(heldViews, preceding.timeSeconds)
      }
      prepared = sourceReference.prepareAt(sourceExposureTimeSeconds)
    }
    if (referenceState !== 'hold-last-readable') {
      // Keep the actual held geometry/camera/layout, not the outgoing fade-to-zero.
      // Opaque holding is deliberately NOT a current-source pixel match.
      for (const view of heldViews) view.composite = { mode: 'opaque' }
      const heldLayout = captureSourceLayout(heldViews)
      for (const view of heldViews) view.sourceLayout = heldLayout
    }
    const hold = sourceReference.commitPrepared()
    sourceSampleTimeSeconds = hold.timeSeconds
    referenceState = hold.state
    activeViews = heldViews
    configureLandmarkProbe()
    if (heldViews.length) drawSourceViews(heldViews, timeSeconds)
    else {
      // No preceding readable exposure exists: keep the genuine displayed manual
      // scene, never blank the canvas or fabricate a source pose.
      sourceDrawTimeSeconds = timeSeconds
      sourceDrawRevision++
      sourceDrawLayout = []
      viewer.render(currentAssembly.state)
    }
    modelTime = timeSeconds
    paintRevision = 'clean'
    notice(sourceError, hold.reason)
    return
  }
  if (prepared.state !== 'unavailable') {
    validateSourceViews(prepared.views)
    viewer.preflightViews(prepared.views)
  }
  const sample = sourceReference.commitPrepared()
  sourceSampleTimeSeconds = sample.timeSeconds
  referenceState = sample.state
  activeViews = sample.views
  configureLandmarkProbe()
  if (sample.state === 'unavailable') {
    notice(sourceError, sample.reason)
    renderPending()
    return
  }
  const chosen = primaryView()
  if (chosen) copyInput(chosen.input)
  drawSourceViews(sample.views, timeSeconds)
  paintRevision = 'clean'
  modelTime = timeSeconds
  notice(physicsError, '')
  notice(sourceError, sourceReference.approximationMessage)
}

function beforeView(_view: SourceView, index: number): void {
  const sample = activeViews[index]
  if (sample) applyView(sample)
}

function updateHud(inputMode: 'sync' | 'preserve' = 'sync'): void {
  const time = player?.getTime() ?? 0
  if (player && isSourceVideoPlayer(player) && manualSourceSeek === 'idle' && document.activeElement !== sourceScrub) {
    sourceScrub.value = String(time)
    sourceScrubTime.value = `${time.toFixed(3)} s`
  }
  const chosen = mode === 'exploring' ? undefined : primaryView()
  const context = mode === 'exploring'
    ? explorationOrigin === 'chosen-feasible-reconstruction' ? 'Manual exploration from chosen feasible reconstruction (not recovered history)' : 'Manual exploration'
    : mode === 'reference-review' && referenceSeek !== 'idle' ? 'Seeking original exposure; retaining the displayed model until real native presentation'
      : referenceState === 'approximate' ? 'Approximate source-following; chosen inputs, not recovered history or a final matched result'
      : referenceState === 'hold-last-readable' ? 'Holding the last readable approximation; no current-source match' : 'Source pose unavailable'
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
  if (inputMode === 'sync') {
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
  invalidateNativeDiagnosticLease('Manual mechanism input changed')
  if (mode !== 'exploring' || modelState !== 'ready') return
  action()
  manualSceneOwnership = 'owned'
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
  const localOriginal = new URLSearchParams(location.search).get('referenceMedia') === '1'
  invalidateNativeDiagnosticLease('The selected native/source context changed')
  selectionAbort?.abort()
  const selection = new AbortController()
  selectionAbort = selection
  player?.destroy()
  player = null
  reference = null
  presentedSampleTimes.clear()
  activeViews = []
  explorationOrigin = 'interactive-default'
  currentAssembly = OPERATING_SOURCE_ASSEMBLY
  configureLandmarkProbe()
  referenceSeek = 'idle'
  manualSourceSeek = 'idle'
  sourceControls.dataset.state = 'idle'
  sourceControls.setAttribute('aria-busy', 'false')
  sourceSeekStatus.textContent = 'Pause to choose an original exposure.'
  sourceScrub.value = '0'
  sourceScrubTime.value = '0.000 s'
  video = next
  videoContainer.replaceChildren()
  playbackState = 'unstarted'
  referenceState = 'unavailable'
  modelTime = 0
  sourceSampleTimeSeconds = 0
  copyInput(createMechanismInput())
  manualRevision = 'pending'
  manualSceneOwnership = 'initial'
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
    if (localOriginal) presentedSampleTimes = buildOriginalPresentationSamples(loaded.data.frames)
    reference = loaded
    if (loaded.data.coverage.status === 'blocked') notice(sourceError, `Source coverage is not complete: ${loaded.coverageMessage}`)
    configureLandmarkProbe()
  }).catch((error: unknown) => {
    if (!selection.signal.aborted) notice(sourceError, error instanceof Error ? error.message : String(error))
  })
  try {
    const createPlayer = localOriginal ? createSourceVideoPlayer : createVideoPlayer
    const created = await createPlayer(videoContainer, next.id, (state) => {
      if (selection.signal.aborted) return
      if (playbackState !== state) invalidateNativeDiagnosticLease(`Source playback changed from ${playbackState} to ${state}`)
      playbackState = state
      if (state === 'playing') {
        notice(videoError, '')
        if (player && isSourceVideoPlayer(player) && player.getSeekIntent() === 'manual') {
          // Real decoder playback owns only the source clock; manual inputs/camera stay manual.
        } else if (mode === 'reference-review' && referenceSeek === 'seeking') player?.pause()
        else if (mode === 'reference-review' && referenceSeek === 'preroll') { /* Genuine native preroll owns decoding; retain the displayed model, not a stale sync claim. */ }
        else {
          try { renderSource(player?.getTime() ?? 0); if (referenceState !== 'unavailable') following() }
          catch (error) { notice(physicsError, error instanceof Error ? error.message : String(error)) }
        }
      } else if ((state === 'paused' || state === 'ended') && mode === 'following-video') {
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
  invalidateNativeDiagnosticLease('The selected native/source route changed')
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
  invalidateNativeDiagnosticLease('The native model is being reloaded')
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
  if (nativeDiagnosticLeaseActive && nativeDiagnosticRefusal === null) return
  try {
    if (mode === 'exploring' && manualSourceSeek === 'idle' && player && isSourceVideoPlayer(player)
      && player.getSeekState() === 'idle' && player.getState() === 'playing') retryFollowing()
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
    } else if (mode === 'reference-review' && referenceSeek === 'preroll') {
      // Do not block native frame-presentation callbacks with unrelated CAD draws.
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
canvas.addEventListener('pointerdown', () => { if (mode === 'exploring') manualSceneOwnership = 'owned' })
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
  invalidateNativeDiagnosticLease('Manual crank motion changed')
  if (mode !== 'exploring') return
  manualSceneOwnership = 'owned'
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
sourcePlay.addEventListener('click', () => pauseButton.click())
sourceScrub.addEventListener('input', () => { sourceScrubTime.value = `${Number(sourceScrub.value).toFixed(3)} s` })
sourceSeekButton.addEventListener('click', () => { void seekOriginalManually(Number(sourceSeekTime.value)).catch(() => { /* The transaction displays its bounded refusal. */ }) })
sourceSeekTime.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); sourceSeekButton.click() } })
sourceScrub.addEventListener('change', () => { void seekOriginalManually(Number(sourceScrub.value)).catch(() => { /* The transaction displays its bounded refusal. */ }) })
sourceVolume.addEventListener('input', () => { if (player && isSourceVideoPlayer(player)) { player.setVolume(Number(sourceVolume.value)); updateControlState() } })
sourceMute.addEventListener('click', () => { if (player && isSourceVideoPlayer(player)) { player.setMuted(!player.getMuted()); updateControlState() } })
pauseButton.addEventListener('click', () => {
  if (player?.getState() === 'playing' || player?.getState() === 'buffering') player.pause()
  else player?.play()
})
followButton.addEventListener('click', () => {
  invalidateNativeDiagnosticLease('Source-following was requested')
  if (!player) return
  try {
    renderSource(player.getTime())
    if (referenceState === 'unavailable') return
    if (player.getState() !== 'playing' && player.getState() !== 'buffering') explore()
    else following()
  } catch (error) { notice(physicsError, error instanceof Error ? error.message : String(error)) }
})
fitButton.addEventListener('click', () => {
  invalidateNativeDiagnosticLease('Manual camera fitting was requested')
  if (mode !== 'exploring') return
  manualSceneOwnership = 'owned'
  viewer.fitView()
})
compactButton.addEventListener('click', () => {
  invalidateNativeDiagnosticLease('The player layout changed')
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
for (const type of ['pointerdown', 'wheel'] as const) canvas.addEventListener(type, (event) => {
  if (event.isTrusted) invalidateNativeDiagnosticLease('Manual camera interaction began')
}, { capture: true })

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
      const captureFrame = (): NativeDiagnosticFrame => ({
        input: structuredClone(input), machineInput: structuredClone(actualMachine.input), camera: cameraRecord(), assembly: currentAssembly,
        // Saved ownership is a whole frame, never live pooled PlaybackViews.
        views: structuredClone(activeViews), layout: captureSourceLayout(activeViews), mode, referenceState, modelTime, sourceSampleTimeSeconds, sourceDrawTimeSeconds, sourceDrawRevision, sourceDrawLayout,
        manualMotion, manualRevision, manualSceneOwnership, explorationOrigin, diagnosticReference, diagnosticMachine, physicsState,
        sourceNotice: sourceError.textContent ?? '', physicsNotice: physicsError.textContent ?? '',
        draws: new Map([...mechanismDraws].map(([id, draw]) => [id, structuredClone(draw)])),
        controlsTarget: viewer.controls.target.clone(), controlsEnabled: viewer.controls.enabled,
        enableDamping: viewer.controls.enableDamping, autoRotate: viewer.controls.autoRotate,
        cameraUp: viewer.camera.up.clone(), cameraNear: viewer.camera.near, cameraFar: viewer.camera.far, cameraLayers: viewer.camera.layers.mask,
        cameraScale: viewer.camera.scale.clone(), cameraZoom: viewer.camera.zoom, cameraFocus: viewer.camera.focus,
        cameraFilmGauge: viewer.camera.filmGauge, cameraFilmOffset: viewer.camera.filmOffset, cameraAspect: viewer.camera.aspect,
        cameraView: viewer.camera.view ? { ...viewer.camera.view } : null,
      })
      const saved = {
        ...captureFrame(), canvasStyle: canvas.style.cssText, pixelRatio: viewer.renderer.getPixelRatio(),
        sceneBackground: viewer.scene.background, sceneEnvironment: viewer.scene.environment,
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
      let sourceResumed = false
      let restored = false
      let frameRestorationFailed = false
      let pendingPublicationRefused = false
      const cleanupErrors: unknown[] = []
      const restore = (action: () => void, errors = cleanupErrors) => { try { action() } catch (error) { errors.push(error) } }
      let cleanupAggregates: WeakSet<AggregateError> | undefined
      const throwCleanupFailures = (errors: unknown[], failed: boolean, original: unknown) => {
        if (!errors.length) return
        if (!failed && errors.length === 1) throw errors[0]
        // Only unwrap our own cleanup aggregate, never a caller's AggregateError.
        // A publication and outer-frame failure must retain the original callback
        // as the first error and cause rather than burying it in another wrapper.
        const nested = failed && original instanceof AggregateError && cleanupAggregates?.has(original) ? original : null
        const aggregate = new AggregateError(failed ? nested ? [...nested.errors, ...errors] : [original, ...errors] : errors,
          failed ? 'Native diagnostic callback and cleanup both failed' : 'Native diagnostic cleanup failed',
          { cause: failed ? nested ? nested.cause : original : errors[0] })
        cleanupAggregates ??= new WeakSet<AggregateError>()
        cleanupAggregates.add(aggregate)
        throw aggregate
      }
      const restoreFrame = (frame: NativeDiagnosticFrame) => {
        try {
          mode = frame.mode
          referenceState = frame.referenceState
          activeViews = frame.views
          modelTime = frame.modelTime
          sourceSampleTimeSeconds = frame.sourceSampleTimeSeconds
          manualMotion = frame.manualMotion
          manualSceneOwnership = frame.manualSceneOwnership
          explorationOrigin = frame.explorationOrigin
          diagnosticReference = frame.diagnosticReference
          diagnosticMachine = frame.diagnosticMachine
          copyInput(frame.input)
          updateMachine(frame.machineInput, frame.assembly)
          viewer.setInteraction(mode === 'exploring' ? 'exploring' : 'following-video')
          viewer.controls.enabled = frame.controlsEnabled
          viewer.controls.enableDamping = false
          viewer.controls.autoRotate = false
          viewer.applyCamera(frame.camera)
          // Ownership restores exact solved bits, not normalized authored bits.
          viewer.camera.position.fromArray(frame.camera.positionMetres)
          viewer.camera.quaternion.fromArray(frame.camera.quaternion)
          viewer.camera.up.copy(frame.cameraUp)
          viewer.camera.near = frame.cameraNear
          viewer.camera.far = frame.cameraFar
          viewer.camera.layers.mask = frame.cameraLayers
          viewer.camera.scale.copy(frame.cameraScale)
          viewer.camera.zoom = frame.cameraZoom
          viewer.camera.focus = frame.cameraFocus
          viewer.camera.filmGauge = frame.cameraFilmGauge
          viewer.camera.filmOffset = frame.cameraFilmOffset
          viewer.camera.aspect = frame.cameraAspect
          viewer.camera.view = frame.cameraView ? { ...frame.cameraView } : null
          viewer.camera.updateProjectionMatrix()
          viewer.camera.updateMatrixWorld(true)
          viewer.controls.target.copy(frame.controlsTarget)
          if (frame.mode !== 'exploring' && frame.views.length) drawSourceViews(frame.views, frame.modelTime)
          else viewer.render(frame.assembly.state)
          sourceDrawRevision = frame.sourceDrawRevision
          sourceDrawTimeSeconds = frame.sourceDrawTimeSeconds
          sourceDrawLayout = frame.sourceDrawLayout
          mechanismDraws.clear()
          for (const [id, draw] of frame.draws) mechanismDraws.set(id, draw)
          physicsState = frame.physicsState
          manualRevision = frame.manualRevision
          paintRevision = 'clean'
          notice(sourceError, frame.sourceNotice)
          notice(physicsError, frame.physicsNotice)
        } catch (error) {
          // A diagnostic candidate may already occupy the canvas. Even a
          // preflight capacity refusal cannot certify the saved normal frame.
          frameRestorationFailed = true
          referenceState = 'unavailable'
          physicsState = 'unavailable'
          activeViews = []
          sourceDrawLayout = []
          mechanismDraws.clear()
          manualMotion = 'idle'
          manualRevision = 'clean'
          paintRevision = 'pending'
          const message = error instanceof Error ? error.message : String(error)
          notice(sourceError, `Native frame restoration failed: ${message}`)
          notice(physicsError, message)
          // Keep a superseding input event's DOM value for its action consumer.
          updateHud('preserve')
          throw error
        } finally {
          restore(() => { viewer.controls.enableDamping = frame.enableDamping })
          restore(() => { viewer.controls.autoRotate = frame.autoRotate })
          manualRunButton.textContent = manualMotion === 'turning' ? 'Stop crank' : 'Turn crank'
        }
      }
      const resumeSource = () => {
        if (sourceResumed) return
        sourceResumed = true
        // Reestablish the real frame/resources synchronously before ordinary
        // intent; no action consumer can start from a diagnostic candidate.
        for (const { key, value } of originals) restore(() => { Object.defineProperty(viewer.renderer, key, { configurable: true, writable: true, value }) })
        for (const { key, value } of glOriginals) restore(() => { Object.defineProperty(gl, key, { configurable: true, writable: true, value }) })
        restore(() => { canvas.style.cssText = saved.canvasStyle })
        restore(() => { viewer.renderer.setPixelRatio(saved.pixelRatio); viewer.resize() })
        viewer.scene.background = saved.sceneBackground
        viewer.scene.environment = saved.sceneEnvironment
        restore(() => { viewerLease.restoreProbes() })
        if (machine === actualMachine && reference === actualReference && player === actualPlayer) restore(() => {
          restoreFrame(saved)
          restored = true
        })
        restore(() => { viewerLease.release() })
        lastTick = performance.now()
        updateControlState()
        // The initiating input event already changed its DOM value. Refreshing
        // the HUD here would replace that intent before the action reads it.
      }
      resumeNativeDiagnosticSource = resumeSource
      const ownsSourceState = () => {
        if (machine !== actualMachine || reference !== actualReference || player !== actualPlayer) {
          invalidateNativeDiagnosticLease('The selected native/source context changed')
        } else if (actualPlayer?.getState() !== actualPlaybackState || actualPlayer?.getTime() !== actualSourceTime) {
          invalidateNativeDiagnosticLease('The actual source playback state or clock changed')
        }
        return nativeDiagnosticRefusal === null
      }
      const requireLease = () => {
        if (!contextLive || !nativeDiagnosticLeaseActive) throw new Error('The native diagnostic lease expired')
        if (!ownsSourceState()) throw new Error(`The native diagnostic lease was superseded: ${nativeDiagnosticRefusal}`)
      }
      let callbackFailed = false
      let callbackError: unknown
      try {
        const result = await run({
          metadata: { sourceProof: false, sourceAcceptance: false, method: 'current-native-scoped-diagnostic-lease' },
          snapshot() { requireLease(); return structuredClone({ ...bridge.snapshot(), sourceProof: false, sourceAcceptance: false }) },
          nativePrimitiveSnapshot() { requireLease(); return unavailableNativePrimitiveSnapshot('Native capture is suspended during diagnostic-only rendering', 'stale') },
          readNativeDrawMetadata() { requireLease(); return viewerLease.readNativeDrawMetadata() },
          readNativeTargetSurfaceAssociation(request) {
            requireLease()
            const result = viewerLease.readNativeTargetSurfaceAssociation(request)
            // Target records are owned except for filtered live draw callbacks.
            if (result.target) result.target.record.renderSubmissions = structuredClone(result.target.record.renderSubmissions)
            return result
          },
          readRegisteredNativeLandmarkAnchors() { requireLease(); return viewerLease.readRegisteredNativeLandmarkAnchors() },
          resolveNativeStagePixelFromSourcePixel(viewId, sourcePixels) { requireLease(); return viewerLease.resolveNativeStagePixelFromSourcePixel(viewId, sourcePixels) },
          measureNativeTargetShaderFeedback(request) {
            requireLease()
            const result = viewerLease.measureNativeTargetShaderFeedback(request)
            if (result.target) result.target.record.renderSubmissions = structuredClone(result.target.record.renderSubmissions)
            return result
          },
          async withPublicationSamples(samples, anchors, callback) {
            requireLease()
            if (!actualReference || publicationActive || typeof callback !== 'function') throw new Error('Diagnostic publication requires the same loaded source reference and a single callback')
            publicationActive = true
            const publicationState = captureFrame()
            let publicationFailed = false
            let publicationError: unknown
            try {
              viewer.setLandmarkProbe(actualMachine.createLandmarkProbe(anchors))
              return await actualReference.withDiagnosticSamples(samples, async (state: DiagnosticSourcePublicationState) => {
                let active = true
                const requireTransaction = () => { requireLease(); if (!active) throw new Error('The diagnostic publication transaction has expired') }
                const transaction: NativeDiagnosticPublication = {
                  implementation: { renderSourceText: renderSource.toString(), prepareAtText: state.prepareAtImplementation, commitPreparedText: state.commitPreparedImplementation },
                  renderSource(timeSeconds) { requireTransaction(); renderSource(timeSeconds, state.reference) },
                  snapshot() {
                    requireTransaction()
                    return { ...state.snapshot(), sourceProof: false, sourceAcceptance: false, activeViews: structuredClone(activeViews),
                      referenceState, modelTime, sourceSampleTimeSeconds, sourceDrawRevision, paintRevision, externalInput: structuredClone(serializeInput(input)) }
                  },
                }
                try {
                  const value = await callback(transaction)
                  requireTransaction()
                  return value
                } finally { active = false }
              })
            } catch (error) {
              publicationFailed = true
              publicationError = error
              throw error
            } finally {
              const errors: unknown[] = []
              try {
                // Local context expiry, not a global active flag, prevents a
                // late callback from restoring over another owner or lease.
                if (contextLive && !sourceResumed && ownsSourceState()) {
                  // beginNativeDiagnosticViewerLease owns the saved outer
                  // probes. Between publications its exact state is null/null.
                  restore(() => { viewer.setLandmarkProbe(null) }, errors)
                  restore(() => { viewer.setPartVisibilityProbe(null) }, errors)
                  restore(() => { restoreFrame(publicationState) }, errors)
                }
              } finally { publicationActive = false }
              throwCleanupFailures(errors, publicationFailed, publicationError)
            }
          },
        })
        if (publicationActive) {
          pendingPublicationRefused = true
          throw new Error('The native diagnostic lease callback returned with a publication still pending; await withPublicationSamples before returning')
        }
        requireLease()
        return result
      } catch (error) {
        callbackFailed = true
        callbackError = error
        throw error
      } finally {
        contextLive = false
        const owned = ownsSourceState()
        try { resumeSource() } finally {
          resumeNativeDiagnosticSource = null
          nativeDiagnosticLeaseActive = false
          lastTick = performance.now()
          // New-owner draws/errors use the normal tick, never cleanup.
          configureLandmarkProbe()
          lastNativeDiagnosticRestoration = {
            status: cleanupErrors.length || frameRestorationFailed || pendingPublicationRefused ? 'failed' : owned && restored ? 'restored' : 'superseded', sourceProof: false, sourceAcceptance: false,
            inputRestored: owned && restored && !frameRestorationFailed && equalRecord(serializeInput(input), serializeInput(saved.input)),
            cameraRestored: owned && restored && !frameRestorationFailed && equalRecord(cameraRecord(), saved.camera),
            assemblyRestored: owned && restored && !frameRestorationFailed && equalRecord(currentAssembly.state, saved.assembly.state),
            layoutRestored: owned && restored && !frameRestorationFailed && equalRecord(captureSourceLayout(activeViews), saved.layout), paintRevision,
            refusalReason: nativeDiagnosticRefusal,
          }
          throwCleanupFailures(cleanupErrors, callbackFailed, callbackError)
        }
      }
    },
    snapshot() {
      const chosen = mode === 'exploring' ? undefined : primaryView()
      const sourceLayout = verificationEnabled ? captureSourceLayout(activeViews) : chosen?.sourceLayout ?? []
      return {
        videoId: video?.id ?? null, playerVideoId: player?.getVideoId() ?? null, mode, playerState: player?.getState() ?? playbackState,
        videoTime: player?.getTime() ?? null, modelTime, sourceSampleTimeSeconds, referenceState, modelState, missingBindings: machine?.missing ?? [],
        sourcePresentation: player && isSourceVideoPlayer(player) ? player.getPresentation() : null,
        sourceSeek: player && isSourceVideoPlayer(player) ? { state: player.getSeekState(), intent: player.getSeekIntent() } : null,
        modelProvenance: machine?.provenance ?? null, camera: cameraRecord(), input: serializeInput(input),
        diagnosticLease: { active: nativeDiagnosticLeaseActive, restoration: lastNativeDiagnosticRestoration },
        sourceDrawRevision, sourceDrawTimeSeconds, diagnosticCapture: physicsState === 'available' && paintRevision === 'clean' && referenceState === 'approximate' && diagnosticReference !== null && diagnosticReference === reference && diagnosticMachine === machine && mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused' ? 'paused-reference-review' : 'disabled',
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
        && draw.viewId !== EXPLORING_VIEW_ID && referenceState === 'approximate' && draw.timeSeconds === modelTime
        && activeViews.some(view => view.id === draw.viewId && (view.composite?.mode !== 'crossfade' || view.composite.opacity > 0)
          && equalRecord(view.sourceAssembly ?? OPERATING_SOURCE_ASSEMBLY.state, draw.sourceAssembly))
      return { ...capture, context: {
        videoId: video?.id ?? null, playerVideoId: player?.getVideoId() ?? null, mode,
        playerState: player?.getState() ?? playbackState, videoTimeSeconds: player?.getTime() ?? null,
        modelTimeSeconds: modelTime, sourceSampleTimeSeconds, sourceDrawRevision, sourceDrawTimeSeconds, referenceState,
        inputMeaning: currentInputMeaning(draw?.viewId),
        sourceFollowing: mode === 'exploring' ? 'disabled-manual-mode' : referenceState === 'hold-last-readable' ? 'held-readable-not-current-source-qualified' : sourceBound ? 'chosen-feasible-not-source-qualified' : 'unavailable',
        nativeDrawViewId: draw?.viewId ?? null, nativeGeometryIssues: capture.manifest?.issues ?? null,
        sourceAssembly: draw?.sourceAssembly ?? null,
        manualMotion, referenceSeek, physicsState, modelState,
      } }
    },
    compactData() { return reference?.data ?? null },
    pauseVideo() { player?.pause(); return this.snapshot() },
    playVideo() { player?.play(); return this.snapshot() },
    async seekVideo(timeSeconds: number) {
      const presented = await seekOriginalManually(timeSeconds)
      return { presentation: presented, snapshot: this.snapshot() }
    },
    async reviewReferenceFrame(timeSeconds: number, sourceTimeSeconds = timeSeconds) {
      invalidateNativeDiagnosticLease('A native reference review was requested')
      const nativePlayer = player
      if (nativePlayer?.getState() !== 'paused') throw new Error('Pause the actual source video before reviewing a reference frame.')
      if (!reference) throw new Error('Source observations are unavailable.')
      if (physicsState !== 'available') throw new Error('Restore a valid mechanical setup before reviewing a source frame.')
      if (referenceSeek !== 'idle') throw new Error('A native reference seek is already active.')
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
      const previousAssembly = currentAssembly
      try {
        mode = 'reference-review'
        referenceSeek = isSourceVideoPlayer(nativePlayer) ? 'preroll' : 'seeking'
        viewer.setInteraction('following-video')
        updateControlState()
        const sourceMedia = videoContainer.querySelector('video')
        const seekTime = sourceMedia && sourceTimeSeconds >= sourceMedia.duration && sourceTimeSeconds - sourceMedia.duration <= 0.5 ? Math.max(0, sourceMedia.duration - 1e-6) : sourceTimeSeconds
        if (isSourceVideoPlayer(nativePlayer)) {
          await nativePlayer.seek(seekTime, 'reference-review')
        } else {
          nativePlayer.seek(seekTime)
          await new Promise<void>((resolve) => window.setTimeout(resolve, 40))
          const deadline = performance.now() + 20_000
          while (nativePlayer.getState() !== 'paused' || Math.abs(nativePlayer.getTime() - seekTime) > 0.002 || sourceMedia && (sourceMedia.seeking || sourceMedia.readyState < HTMLMediaElement.HAVE_CURRENT_DATA)) {
            if (nativePlayer !== player) throw new Error('The source video changed during reference review.')
            if (nativePlayer.getState() === 'error' || nativePlayer.getState() === 'ended') throw new Error('The actual source video cannot display the requested reference time.')
            if (performance.now() >= deadline) throw new Error('The actual source video did not settle at the requested paused reference time.')
            await new Promise<void>((resolve) => window.setTimeout(resolve, 40))
          }
        }
        if (nativePlayer !== player) throw new Error('The source video changed during reference review.')
        referenceSeek = 'idle'
        const presented = isSourceVideoPlayer(nativePlayer) ? nativePlayer.getPresentation() : null
        if (isSourceVideoPlayer(nativePlayer) && !presented) throw new Error('The actual original source presentation was superseded before drawing.')
        // Select pose/readability from the verified original exposure, but draw
        // and model clocks remain the real paused media clock, never target time.
        renderSource(isSourceVideoPlayer(nativePlayer) ? nativePlayer.getTime() : timeSeconds, reference,
          presented ? presented.pts * presented.timeBase[0] / presented.timeBase[1] : timeSeconds)
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
      invalidateNativeDiagnosticLease('Manual exploration was requested')
      if (player?.getState() !== 'paused') throw new Error('Pause the actual source video before entering manual exploration.')
      if (referenceSeek !== 'idle') throw new Error('Wait for the active native reference seek before entering manual exploration.')
      explore()
      return this.snapshot()
    },
    renderedLandmarks(viewId: string) {
      if (mode !== 'reference-review' || referenceSeek !== 'idle' || referenceState !== 'approximate' || player?.getState() !== 'paused') return null
      const capture = viewer.readRenderedLandmarks(viewId)
      return capture ? sourceCapture(capture) : null
    },
    renderedPartVisibility(viewId: string) {
      const native = viewer.readRenderedPartVisibility(viewId)
      const capture = referenceState === 'hold-last-readable'
        ? { ...native, sourceProof: false as const, sourceAcceptance: false as const, sourceFollowing: 'held-readable-not-current-source-qualified' as const }
        : sourceCapture(native)
      return mode === 'reference-review' && referenceSeek === 'idle' && player?.getState() === 'paused' ? capture : { ...capture, status: 'unavailable' as const, parts: [] }
    },
    enablePartVisibility() {
      if (mode !== 'reference-review' || referenceSeek !== 'idle' || !['approximate', 'hold-last-readable'].includes(referenceState) || player?.getState() !== 'paused') throw new Error('Pause and review an actual source frame or explicitly held readable native pose before enabling native visibility capture.')
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
