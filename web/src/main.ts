import { createViewer, loadMachine, type Machine } from './scene'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { MAGNIFIER_RATIO_MAX, MAGNIFIER_RATIO_MIN, squareWave } from './kinematics'
import { loadTrack, type Track, type TrackView } from './track'
import { createVideoPlayer, type PlaybackState, type VideoPlayer } from './youtube-player'
import { VIDEOS, resolveVideo, type Video } from './video-catalog'

function element<T extends HTMLElement>(selector: string): T {
  const found = document.querySelector<T>(selector)
  if (!found) throw new Error(`Missing ${selector}`)
  return found
}

const canvas = element<HTMLCanvasElement>('#stage')
const loading = element('#loading')
const modelStatus = element('#model-status')
const modelProgress = element<HTMLProgressElement>('#model-progress')
const retryModel = element<HTMLButtonElement>('#retry-model')
const title = element('#video-title')
const playbackStatus = element('#playback-status')
const playbackClock = element('#playback-clock')
const modelError = element('#model-error')
const videoError = element('#video-error')
const videoContainer = element('#video-player')
const videoDock = element('#video-dock')
const workspace = element('#workspace')
const pauseButton = element<HTMLButtonElement>('#pause-video')
const followButton = element<HTMLButtonElement>('#follow-video')
const fitButton = element<HTMLButtonElement>('#fit-view')
const compactButton = element<HTMLButtonElement>('#minimize-player')
const crank = element<HTMLInputElement>('#crank')
const gearing = element<HTMLSelectElement>('#gearing')
const magnification = element<HTMLInputElement>('#magnification')
const fixture = element<HTMLInputElement>('#fixture-offset')
const cone = element<HTMLInputElement>('#cone-swing')
const pinion = element<HTMLInputElement>('#pinion-cam')
const platen = element<HTMLInputElement>('#platen-offset')
const crankValue = element<HTMLOutputElement>('#crank-value')
const magnificationValue = element<HTMLOutputElement>('#magnification-value')
const fixtureValue = element<HTMLOutputElement>('#fixture-value')
const coneValue = element<HTMLOutputElement>('#cone-value')
const pinionValue = element<HTMLOutputElement>('#pinion-value')
const platenValue = element<HTMLOutputElement>('#platen-value')
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

/** The manual (exploring) mechanism state. */
const input = createMechanismInput()
let machine: Machine | null = null
let track: Track | null = null
let player: VideoPlayer | null = null
let video: Video | null = null
let selection: AbortController | null = null
let playbackState: PlaybackState = 'unstarted'
/** Following draws the shot table at the video time; exploring draws the manual state. */
let mode: 'following-video' | 'exploring' = 'following-video'
let dirty = true
let turning = false
let views: readonly TrackView[] = []
/** ?t= deep link: the time shown before the player reports one. */
let linkedTime = Number(new URLSearchParams(location.search).get('t')) || 0
let lastTick = performance.now()
let lastHud = 0
const channelInputs: { amplitude: HTMLInputElement; phase: HTMLInputElement; value: HTMLOutputElement }[] = []

function notice(target: HTMLElement, message: string): void {
  target.textContent = message
  target.hidden = message === ''
}

function setValue(control: HTMLInputElement | HTMLSelectElement | HTMLOutputElement, value: string): void {
  if (document.activeElement !== control && control.value !== value) control.value = value
}

function videoTime(): number {
  return player && playbackState !== 'unstarted' && playbackState !== 'cued' ? player.getTime() : linkedTime
}

/** The largest tile stands for the frame when the user takes over. */
function primaryView(): TrackView | undefined {
  let best: TrackView | undefined
  for (const view of views) if (!best || view.rect[2] * view.rect[3] > best.rect[2] * best.rect[3]) best = view
  return best
}

function explore(): void {
  if (mode === 'exploring') return
  const primary = primaryView()
  if (primary) {
    copyInput(primary.input, input)
    viewer.applyCamera(primary.camera)
  }
  mode = 'exploring'
  viewer.setInteraction('exploring')
  dirty = true
}

function follow(): void {
  mode = 'following-video'
  turning = false
  manualRunButton.textContent = 'Turn crank'
  viewer.setInteraction('following-video')
  dirty = true
}

function copyInput(source: MechanismInput, target: MechanismInput): void {
  target.crankTurns = source.crankTurns
  target.amplitudes.set(source.amplitudes)
  target.phases.set(source.phases)
  target.gearing = source.gearing
  target.magnification = source.magnification
  Object.assign(target.setup, source.setup)
}

function editMechanism(action: () => void): void {
  explore()
  action()
  dirty = true
  updateHud()
}

function updateHud(): void {
  const time = videoTime()
  const status = `${stateLabels[playbackState]} · ${mode === 'exploring' ? 'Exploring' : track ? 'Following the video' : 'No shot table for this video'}`
  if (playbackStatus.textContent !== status) playbackStatus.textContent = status
  const clock = ` · ${time.toFixed(1)} s`
  if (playbackClock.textContent !== clock) playbackClock.textContent = clock
  pauseButton.disabled = !player
  pauseButton.textContent = playbackState === 'playing' || playbackState === 'buffering' ? 'Pause & explore' : 'Play video'
  followButton.disabled = !track || mode === 'following-video'
  const shown = mode === 'exploring' ? input : primaryView()?.input ?? input
  setValue(crank, String(shown.crankTurns))
  setValue(crankValue, `${shown.crankTurns.toFixed(3)} turns`)
  setValue(gearing, shown.gearing)
  setValue(magnification, String(shown.magnification))
  setValue(fixture, String(shown.setup.wireFixtureOffsetM))
  setValue(cone, String(shown.setup.coneSwingRad))
  setValue(pinion, String(shown.setup.pinionCamRad))
  setValue(platen, String(shown.setup.platenOffsetM))
  setValue(magnificationValue, `${shown.magnification.toFixed(3)}×`)
  setValue(fixtureValue, `${(shown.setup.wireFixtureOffsetM * 1000).toFixed(1)} mm`)
  setValue(coneValue, `${(shown.setup.coneSwingRad * 180 / Math.PI).toFixed(2)}°`)
  setValue(pinionValue, `${(shown.setup.pinionCamRad * 180 / Math.PI).toFixed(1)}°`)
  setValue(platenValue, `${(shown.setup.platenOffsetM * 1000).toFixed(1)} mm`)
  channelInputs.forEach((controls, i) => {
    setValue(controls.amplitude, String(shown.amplitudes[i]!))
    setValue(controls.phase, String(shown.phases[i]! * 180 / Math.PI))
    setValue(controls.value, `${(shown.amplitudes[i]! * MECHANISM_DATA.channel.maximumStationMm).toFixed(1)} mm · ${(shown.phases[i]! * 180 / Math.PI).toFixed(0)}°`)
  })
  if (!machine) return
  let minimum = Infinity
  let maximum = -Infinity
  for (const force of machine.pose.springForcesN) {
    minimum = Math.min(minimum, force)
    maximum = Math.max(maximum, force)
  }
  setValue(forceReadout, `20 springs · ${minimum.toFixed(2)}–${maximum.toFixed(2)} N\nTorque residual ${machine.pose.equilibriumResidualNm.toExponential(1)} N·m\nPaper feed ${(machine.pose.platenTravelM * 1000).toFixed(2)} mm`)
}

function buildChannelControls(): void {
  const container = element('#channel-controls')
  for (let i = 0; i < 20; i++) {
    const harmonic = MECHANISM_DATA.harmonicNumbers[i]!
    const row = document.createElement('div')
    row.className = 'channel-row'
    const heading = document.createElement('span')
    heading.textContent = `H${harmonic}`
    const amplitude = Object.assign(document.createElement('input'), { id: `amplitude-${harmonic}`, type: 'range', min: '-1', max: '1', step: '0.001' })
    amplitude.setAttribute('aria-label', `Harmonic ${harmonic} amplitude`)
    const phase = Object.assign(document.createElement('input'), { id: `phase-${harmonic}`, type: 'range', min: '-180', max: '180', step: '1' })
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
    const route = new URL(location.href)
    route.searchParams.set('video', entry.slug)
    route.searchParams.delete('t')
    const link = Object.assign(document.createElement('a'), { href: route.href, textContent: videoLabels[entry.id]!, title: entry.title })
    link.dataset.videoId = entry.id
    link.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      history.pushState(null, '', link.href)
      linkedTime = 0
      void selectVideo(entry)
    })
    navigation.append(link)
  }
}

async function selectVideo(next: Video): Promise<void> {
  selection?.abort()
  const current = new AbortController()
  selection = current
  player?.destroy()
  player = null
  track = null
  views = []
  video = next
  playbackState = 'unstarted'
  videoContainer.replaceChildren()
  copyInput(createMechanismInput(), input)
  follow()
  title.textContent = videoLabels[next.id]!
  document.title = `${videoLabels[next.id]} — Harmonic Analyzer`
  element('#video-label').textContent = videoLabels[next.id]!
  element<HTMLAnchorElement>('#watch-on-youtube').href = `https://www.youtube.com/watch?v=${next.id}`
  for (const link of element('#videos').querySelectorAll<HTMLAnchorElement>('a')) {
    if (link.dataset.videoId === next.id) link.setAttribute('aria-current', 'page')
    else link.removeAttribute('aria-current')
  }
  notice(videoError, '')
  const trackPromise = loadTrack(next.slug).then(loaded => {
    if (current.signal.aborted) return
    track = loaded
    if (!loaded) explore()
    dirty = true
  }).catch((error: unknown) => notice(videoError, `Shot table failed to load: ${error instanceof Error ? error.message : String(error)}`))
  try {
    const created = await createVideoPlayer(videoContainer, next.id, state => {
      if (current.signal.aborted) return
      playbackState = state
      // Playing hands the view back to the video; pausing keeps the frame until the user takes over.
      if (state === 'playing') { notice(videoError, ''); follow() }
      dirty = true
      updateHud()
    }, { signal: current.signal, onError: error => { if (!current.signal.aborted) notice(videoError, error.message) } })
    if (current.signal.aborted) { created.destroy(); return }
    player = created
    playbackState = created.getState()
  } catch (error) {
    if (!current.signal.aborted) notice(videoError, error instanceof Error ? error.message : String(error))
  }
  await trackPromise
  updateHud()
}

function selectRoute(): void {
  try { void selectVideo(resolveVideo(location.search)) } catch (error) {
    selection?.abort()
    player?.destroy()
    player = null
    track = null
    title.textContent = 'Unknown video'
    notice(videoError, error instanceof Error ? error.message : String(error))
  }
}

async function fetchMachine(): Promise<void> {
  machine?.dispose()
  loading.hidden = false
  modelStatus.textContent = 'Loading the CAD model…'
  modelProgress.hidden = false
  modelProgress.removeAttribute('value')
  retryModel.hidden = true
  machine = await loadMachine(viewer.scene, progress => {
    if (progress.phase === 'preparing') { modelStatus.textContent = 'Preparing the model…'; return }
    modelStatus.textContent = `Downloading the CAD model… ${(progress.loadedBytes / 1e6).toFixed(0)} MB`
    if (progress.totalBytes) { modelProgress.max = progress.totalBytes; modelProgress.value = progress.loadedBytes }
  })
  if (machine.available) {
    loading.hidden = true
    machine.update(input)
    viewer.fitView()
  } else {
    modelProgress.hidden = true
    modelStatus.textContent = 'No CAD model loaded. Run npm run fetch-model, then retry.'
    retryModel.hidden = false
  }
  notice(modelError, machine.missing.length ? `Some parts do not move: ${machine.missing.join('; ')}` : '')
  dirty = true
  updateHud()
}

function tick(now: number): void {
  requestAnimationFrame(tick)
  const elapsed = Math.min((now - lastTick) / 1000, 0.25)
  lastTick = now
  if (mode === 'following-video' && track) {
    views = track.evaluate(videoTime())
    if (views.length) viewer.renderViews(views, view => updatePose(view.input))
    else viewer.render()
  } else {
    if (turning) { input.crankTurns += elapsed * Number(speed.value); dirty = true }
    if (dirty) {
      updatePose(input)
      viewer.render()
      dirty = false
    }
  }
  if (now - lastHud >= 100) { updateHud(); lastHud = now }
}

const physicsWarnings = new Set<string>()
/** Pose the model; an input with no physical solution keeps the last pose. */
function updatePose(next: MechanismInput): void {
  try { machine?.update(next) } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (!physicsWarnings.has(message)) { physicsWarnings.add(message); console.warn(`[machine] ${message}`) }
  }
}

const viewer = createViewer(canvas, () => { dirty = true })
new ResizeObserver(() => { viewer.resize(); dirty = true }).observe(canvas.parentElement!)
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
crank.addEventListener('input', () => editMechanism(() => { input.crankTurns = Number(crank.value); turning = false; manualRunButton.textContent = 'Turn crank' }))
gearing.addEventListener('change', () => editMechanism(() => { input.gearing = gearing.value as MechanismInput['gearing'] }))
magnification.addEventListener('input', () => editMechanism(() => { input.magnification = Number(magnification.value) }))
fixture.addEventListener('input', () => editMechanism(() => { input.setup.wireFixtureOffsetM = Number(fixture.value) }))
cone.addEventListener('input', () => editMechanism(() => {
  const nextSwing = Number(cone.value)
  // Swinging the cone out holds the cylinder bank; re-meshing resumes from where it was held.
  if (input.setup.coneSwingRad === 0 && nextSwing !== 0) input.setup.heldChannelTurns = input.crankTurns - input.setup.driveCrankOffsetTurns
  if (input.setup.coneSwingRad !== 0 && nextSwing === 0) input.setup.driveCrankOffsetTurns = input.crankTurns - input.setup.heldChannelTurns
  input.setup.coneSwingRad = nextSwing
}))
pinion.addEventListener('input', () => editMechanism(() => { input.setup.pinionCamRad = Number(pinion.value) }))
platen.addEventListener('input', () => editMechanism(() => { input.setup.platenOffsetM = Number(platen.value) }))
manualRunButton.addEventListener('click', () => editMechanism(() => {
  turning = !turning
  manualRunButton.textContent = turning ? 'Stop crank' : 'Turn crank'
}))
element('#zero-coefficients').addEventListener('click', () => editMechanism(() => { input.amplitudes.fill(0) }))
element('#fundamental-coefficient').addEventListener('click', () => editMechanism(() => {
  for (let i = 0; i < 20; i++) input.amplitudes[i] = MECHANISM_DATA.harmonicNumbers[i] === 1 ? 0.4 : 0
}))
element('#odd-coefficients').addEventListener('click', () => editMechanism(() => {
  const coefficients = squareWave(6)
  for (let i = 0; i < 20; i++) input.amplitudes[i] = coefficients[MECHANISM_DATA.harmonicNumbers[i]! - 1]! / 10
}))
pauseButton.addEventListener('click', () => {
  if (playbackState === 'playing' || playbackState === 'buffering') { player?.pause(); explore(); return }
  // YouTube's seekTo starts a cued video, so a ?t= deep link is applied on the first play.
  if ((playbackState === 'unstarted' || playbackState === 'cued') && linkedTime > 0) player?.seek(linkedTime)
  else player?.play()
})
followButton.addEventListener('click', follow)
fitButton.addEventListener('click', () => { explore(); viewer.fitView(); dirty = true })
compactButton.addEventListener('click', () => {
  const compact = videoDock.dataset.size !== 'compact'
  videoDock.dataset.size = compact ? 'compact' : 'expanded'
  workspace.dataset.playerSize = videoDock.dataset.size
  compactButton.textContent = compact ? 'Expand player' : 'Compact player'
  compactButton.setAttribute('aria-expanded', String(!compact))
  viewer.resize()
  dirty = true
})
retryModel.addEventListener('click', () => { void fetchMachine() })
window.addEventListener('popstate', () => { linkedTime = Number(new URLSearchParams(location.search).get('t')) || 0; selectRoute() })
for (const type of ['pointerdown', 'wheel'] as const) canvas.addEventListener(type, event => { if (event.isTrusted) explore() }, { capture: true })

selectRoute()
void fetchMachine()
requestAnimationFrame(tick)

if (new URLSearchParams(location.search).get('edit') === '1') {
  void import('./editor').then(({ startEditor }) => startEditor({
    viewer, input,
    get player() { return player },
    get track() { return track },
    get video() { return video },
    time: videoTime,
    explore: () => { explore(); dirty = true },
    redraw: () => { dirty = true },
  }))
}
