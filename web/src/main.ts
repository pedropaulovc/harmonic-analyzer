import { createViewer, loadMachine, type CameraRecord, type Machine, type SourceView } from './scene'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_MAX, squareWave } from './kinematics'
import { VIDEOS, resolveVideo, type Video } from './video-catalog'
import { createVideoPlayer, type PlaybackState, type VideoPlayer } from './youtube-player'
import { loadReference, serializeInput, type PlaybackView, type ReferenceState, type VideoReference } from './timeline'

function element<T extends HTMLElement>(selector: string): T {
  const found = document.querySelector<T>(selector)
  if (!found) throw new Error(`Missing page element: ${selector}`)
  return found
}

const canvas = element<HTMLCanvasElement>('#stage')
const loading = element('#loading')
const modelStatus = element('#model-status')
const retryModel = element<HTMLButtonElement>('#retry-model')
const title = element('#video-title')
const status = element('#status')
const sourceError = element('#source-error')
const modelError = element('#model-error')
const physicsError = element('#physics-error')
const videoError = element('#video-error')
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
  rMHw9GCAtE8: 'PDF guide', XPQwKRt4Y2k: 'Machine spin', '4mBuyixt22U': 'Rocker arms',
}
const stateLabels: Record<PlaybackState, string> = {
  unstarted: 'Ready to play', cued: 'Ready to play', playing: 'Playing', paused: 'Paused',
  buffering: 'Buffering', ended: 'Video ended', error: 'Playback unavailable',
}
const input = createMechanismInput()
const reviewRollbackInput = createMechanismInput()
let machine: Machine | null = null
let reference: VideoReference | null = null
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
let lastTick = performance.now()
let lastHud = 0
const channelInputs: { amplitude: HTMLInputElement; phase: HTMLInputElement; value: HTMLOutputElement }[] = []

function notice(target: HTMLElement, message: string): void {
  target.textContent = message
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
  viewer.setLandmarkProbe(null)
  if (new URLSearchParams(location.search).get('verify') !== '1') return
  if (!reference || machine?.availability !== 'available') return
  viewer.setLandmarkProbe(machine.createLandmarkProbe(reference.data.anchors))
}

function renderPending(): void {
  if (paintRevision === 'clean') return
  paintRevision = 'clean'
  viewer.render()
}

function updateMachine(source: MechanismInput, overrides?: PlaybackView['partOverrides']): void {
  if (machine?.availability !== 'available') return
  physicsState = 'unavailable'
  machine.update(source, overrides)
  physicsState = 'available'
  paintRevision = 'pending'
}

function primaryView(): PlaybackView | undefined {
  let selected: PlaybackView | undefined
  let area = -1
  for (const view of activeViews) {
    const nextArea = view.rectSourcePixels[2] * view.rectSourcePixels[3]
    if (nextArea > area) { area = nextArea; selected = view }
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

function explore(): void {
  const chosen = primaryView()
  if (chosen && machine?.availability === 'available') {
    copyInput(chosen.input)
    updateMachine(input, chosen.partOverrides)
    viewer.applyCamera(chosen.camera)
  }
  mode = 'exploring'
  manualMotion = 'idle'
  manualRunButton.textContent = 'Turn crank'
  viewer.setInteraction('exploring')
  updateControlState()
  updateHud()
  paintRevision = 'pending'
}

function following(): void {
  mode = 'following-video'
  manualMotion = 'idle'
  manualRunButton.textContent = 'Turn crank'
  viewer.setInteraction('following-video')
  updateControlState()
}

function applyView(view: PlaybackView): void {
  if (!machine || machine.availability !== 'available') return
  updateMachine(view.input, view.partOverrides)
}

function renderSource(timeSeconds: number): void {
  if (!reference || !machine || machine.availability !== 'available') {
    referenceState = 'unavailable'
    renderPending()
    return
  }
  const sample = reference.at(timeSeconds)
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
    viewer.renderViews(sample.views, beforeView, timeSeconds)
    paintRevision = 'clean'
  }
  modelTime = timeSeconds
  notice(physicsError, '')
  if (reference.data.coverage.status === 'blocked') {
    notice(sourceError, `Source coverage is not complete: ${reference.coverageMessage}`)
  } else {
    notice(sourceError, '')
  }
}

function beforeView(_view: SourceView, index: number): void {
  const sample = activeViews[index]
  if (sample) applyView(sample)
}

function updateHud(): void {
  const time = player?.getTime() ?? 0
  const context = mode === 'exploring' ? 'Manual exploration' : referenceState === 'held' ? 'Holding last matched machine pose' : referenceState === 'matched' ? 'Following measured source pose' : referenceState === 'no-machine' ? 'No corresponding machine in this source interval' : 'Source pose not verified'
  status.textContent = `${stateLabels[playbackState]} · ${time.toFixed(1)} s · ${context}`
  crank.value = String(input.crankTurns)
  element<HTMLOutputElement>('#crank-value').value = `${input.crankTurns.toFixed(3)} turns`
  gearing.value = input.gearing
  magnification.value = String(input.magnification)
  fixture.value = String(input.setup.wireFixtureOffsetM)
  cone.value = String(input.setup.coneSwingRad)
  pinion.value = String(input.setup.pinionCamRad)
  platen.value = String(input.setup.platenOffsetM)
  element<HTMLOutputElement>('#magnification-value').value = `${input.magnification.toFixed(3)}×`
  element<HTMLOutputElement>('#fixture-value').value = `${(input.setup.wireFixtureOffsetM * 1000).toFixed(1)} mm`
  element<HTMLOutputElement>('#cone-value').value = `${(input.setup.coneSwingRad * 180 / Math.PI).toFixed(2)}°`
  element<HTMLOutputElement>('#pinion-value').value = `${(input.setup.pinionCamRad * 180 / Math.PI).toFixed(1)}°`
  element<HTMLOutputElement>('#platen-value').value = `${(input.setup.platenOffsetM * 1000).toFixed(1)} mm`
  for (let i = 0; i < channelInputs.length; i++) {
    const controls = channelInputs[i]!
    controls.amplitude.value = String(input.amplitudes[i]!)
    controls.phase.value = String(input.phases[i]! * 180 / Math.PI)
    controls.value.value = `${(input.amplitudes[i]! * MECHANISM_DATA.channel.maximumStationMm).toFixed(1)} mm · ${(input.phases[i]! * 180 / Math.PI).toFixed(0)}°`
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
  forceReadout.value = `20 springs · ${minimum.toFixed(2)}–${maximum.toFixed(2)} N\nTorque residual ${machine.pose.equilibriumResidualNm.toExponential(1)} N·m\nPaper feed ${(machine.pose.platenTravelM * 1000).toFixed(2)} mm`
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
    link.href = `?video=${entry.slug}`
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
  viewer.setLandmarkProbe(null)
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
    const created = await createVideoPlayer(videoContainer, next.id, (state) => {
      if (selection.signal.aborted) return
      playbackState = state
      if (state === 'playing') {
        notice(videoError, '')
        if (mode === 'reference-review' && referenceSeek === 'seeking') player?.pause()
        else following()
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
  if (!selection.signal.aborted) { updateControlState(); updateHud() }
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
    viewer.setLandmarkProbe(null)
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
    notice(modelError, machine.missing.length ? `Unresolved native joints: ${machine.missing.join(', ')}. This model cannot establish complete footage fidelity.` : '')
    configureLandmarkProbe()
    manualRevision = 'clean'
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
      if (activeViews.length) viewer.renderViews(activeViews, beforeView, modelTime)
      else renderPending()
      paintRevision = 'clean'
    }
  } catch (error) {
    manualMotion = 'idle'
    manualRevision = 'clean'
    physicsState = 'unavailable'
    manualRunButton.textContent = 'Turn crank'
    referenceState = 'unavailable'
    notice(physicsError, error instanceof Error ? error.message : String(error))
    renderPending()
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
  renderSource(player.getTime())
  if (player.getState() !== 'playing' && player.getState() !== 'buffering') explore()
  else following()
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

if (new URLSearchParams(location.search).get('verify') === '1') {
  const bridge = {
    snapshot() {
      return {
        videoId: video?.id ?? null, playerVideoId: player?.getVideoId() ?? null, mode, playerState: player?.getState() ?? playbackState,
        videoTime: player?.getTime() ?? null, modelTime, referenceState, modelState, missingBindings: machine?.missing ?? [],
        modelProvenance: machine?.provenance ?? null, camera: cameraRecord(), input: serializeInput(input),
        physics: machine && physicsState === 'available' ? { springForcesN: Array.from(machine.pose.springForcesN), springLengthsM: Array.from(machine.pose.springLengthsM), equilibriumResidualNm: machine.pose.equilibriumResidualNm, platenTravelM: machine.pose.platenTravelM, summingAngleRad: machine.pose.summingAngleRad } : null,
        playerAudio: player?.getAudio() ?? null,
        views: activeViews.map((view) => ({ id: view.id, rectSourcePixels: view.rectSourcePixels, presentation: view.presentation, camera: view.camera, input: serializeInput(view.input) })),
      }
    },
    referenceData() { return reference?.data ?? null },
    async reviewReferenceFrame(timeSeconds: number) {
      const nativePlayer = player
      if (nativePlayer?.getState() !== 'paused') throw new Error('Pause the actual source video before reviewing a reference frame.')
      if (!reference) throw new Error('Source observations are unavailable.')
      if (physicsState !== 'available') throw new Error('Restore a valid mechanical setup before reviewing a source frame.')
      if (referenceSeek === 'seeking') throw new Error('A native reference seek is already active.')
      if (!Number.isFinite(timeSeconds) || timeSeconds < 0) throw new Error('Reference time must be finite and nonnegative.')
      if (reference.getState(timeSeconds) === 'unavailable') throw new Error('The requested source frame has no validated corresponding pose.')
      const previousView = mode === 'exploring' ? undefined : primaryView()
      const sourceCamera = previousView?.camera ?? cameraRecord()
      const previousCamera: CameraRecord = {
        positionMetres: [...sourceCamera.positionMetres],
        quaternion: [...sourceCamera.quaternion],
        verticalFovDegrees: sourceCamera.verticalFovDegrees,
      }
      const previousOverrides = previousView?.partOverrides
      copyInput(input, reviewRollbackInput)
      try {
        mode = 'reference-review'
        referenceSeek = 'seeking'
        viewer.setInteraction('following-video')
        updateControlState()
        nativePlayer.seek(timeSeconds)
        await new Promise<void>((resolve) => window.setTimeout(resolve, 40))
        const deadline = performance.now() + 20_000
        while (nativePlayer.getState() !== 'paused' || Math.abs(nativePlayer.getTime() - timeSeconds) > 0.002) {
          if (nativePlayer !== player) throw new Error('The source video changed during reference review.')
          if (nativePlayer.getState() === 'error' || nativePlayer.getState() === 'ended') throw new Error('The actual source video cannot display the requested reference time.')
          if (performance.now() >= deadline) throw new Error('The actual source video did not settle at the requested paused reference time.')
          await new Promise<void>((resolve) => window.setTimeout(resolve, 40))
        }
        if (nativePlayer !== player) throw new Error('The source video changed during reference review.')
        referenceSeek = 'idle'
        renderSource(timeSeconds)
        if (referenceState === 'unavailable') throw new Error('The requested source frame has no validated corresponding pose.')
        return this.snapshot()
      } catch (error) {
        if (nativePlayer === player) {
          referenceSeek = 'idle'
          mode = 'exploring'
          activeViews = []
          referenceState = 'unavailable'
          copyInput(reviewRollbackInput)
          updateMachine(input, previousOverrides)
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
    renderedLandmarks(viewId: string) { return viewer.readRenderedLandmarks(viewId) },
    followVideo() {
      following()
      if (player) renderSource(player.getTime())
      if (player?.getState() !== 'playing' && player?.getState() !== 'buffering') explore()
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
