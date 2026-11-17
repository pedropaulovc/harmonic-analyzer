/**
 * ?edit=1 shot editor: scrub the video, frame a camera (named preset or
 * orbit), set crank turns and the channel preset, then copy a shot row to
 * paste into content/tracks/<slug>.json. Loaded only on ?edit=1.
 */
import type { Viewer } from './scene'
import { MAGNIFIER_RATIO_BUILT, type MechanismInput } from './mechanics'
import { NAMED_CAMERAS, cameraPose, type CameraSpec, type SetupSpec, type Shot, type Track } from './track'
import type { VideoPlayer } from './youtube-player'
import type { Video } from './video-catalog'

export interface EditorContext {
  viewer: Viewer
  /** The live exploring mechanism state. */
  input: MechanismInput
  readonly player: VideoPlayer | null
  readonly track: Track | null
  readonly video: Video | null
  time(): number
  explore(): void
  redraw(): void
}

const round = (value: number, digits: number) => Number(value.toFixed(digits))

function liveCamera(viewer: Viewer): CameraSpec {
  const { camera, controls } = viewer
  const spec: CameraSpec = {
    position: [round(camera.position.x, 5), round(camera.position.y, 5), round(camera.position.z, 5)],
    target: [round(controls.target.x, 5), round(controls.target.y, 5), round(controls.target.z, 5)],
    fov: round(camera.fov, 3),
  }
  if (Math.abs(camera.up.y - 1) > 1e-6) spec.up = [round(camera.up.x, 5), round(camera.up.y, 5), round(camera.up.z, 5)]
  return spec
}

function setupOf(input: MechanismInput): SetupSpec | undefined {
  const setup: SetupSpec = {}
  if (input.gearing !== 'small-large') setup.gearing = input.gearing
  if (Math.abs(input.magnification - MAGNIFIER_RATIO_BUILT) > 1e-9) setup.magnification = round(input.magnification, 6)
  for (const [key, value] of Object.entries(input.setup)) {
    if (value !== null && value !== 0) setup[key as keyof MechanismInput['setup']] = round(value, 7)
  }
  return Object.keys(setup).length ? setup : undefined
}

export function startEditor(context: EditorContext): void {
  const panel = document.createElement('section')
  panel.id = 'shot-editor'
  panel.setAttribute('aria-label', 'Shot editor')
  panel.innerHTML = `
    <h2>Shot editor</h2>
    <label>Video time <output data-id="time">0.000 s</output></label>
    <input data-id="scrub" type="range" min="0" step="0.001" value="0" />
    <div class="row">
      <button data-step="-1">−1 s</button><button data-step="-0.1">−0.1 s</button><button data-frames="-1">−1 frame</button>
      <button data-frames="1">+1 frame</button><button data-step="0.1">+0.1 s</button><button data-step="1">+1 s</button>
    </div>
    <div class="row"><button data-id="mark-start">Start ⟵ now</button><output data-id="start">0.000</output>
      <button data-id="mark-end">End ⟵ now</button><output data-id="end">0.000</output></div>
    <label>Camera <select data-id="camera"><option value="">Orbit (current view)</option></select></label>
    <div class="row"><label>Camera at end <select data-id="camera-end"><option value="">Same as start</option><option value="orbit">Orbit (captured)</option></select></label>
      <button data-id="capture-end">Capture end orbit</button></div>
    <div class="row"><label>Crank turns <input data-id="turns-start" type="number" step="0.01" value="0" /></label>
      <label>to <input data-id="turns-end" type="number" step="0.01" value="0" /></label></div>
    <label>Channel preset <select data-id="preset"></select></label>
    <label>Mode <select data-id="mode"><option>follow</option><option>hold</option></select></label>
    <label><input data-id="unverified" type="checkbox" /> Mark "review": "unverified"</label>
    <div class="row"><button data-id="copy">Copy shot row</button><button data-id="current">Show current row</button></div>
    <textarea data-id="out" rows="6" spellcheck="false"></textarea>`
  document.body.append(panel)
  const get = <T extends HTMLElement>(id: string) => panel.querySelector<T>(`[data-id="${id}"]`)!
  const timeOut = get<HTMLOutputElement>('time')
  const scrub = get<HTMLInputElement>('scrub')
  const startOut = get<HTMLOutputElement>('start')
  const endOut = get<HTMLOutputElement>('end')
  const cameraSelect = get<HTMLSelectElement>('camera')
  const cameraEndSelect = get<HTMLSelectElement>('camera-end')
  const turnsStart = get<HTMLInputElement>('turns-start')
  const turnsEnd = get<HTMLInputElement>('turns-end')
  const presetSelect = get<HTMLSelectElement>('preset')
  const modeSelect = get<HTMLSelectElement>('mode')
  const unverified = get<HTMLInputElement>('unverified')
  const out = get<HTMLTextAreaElement>('out')
  let start = 0
  let end = 0
  let endOrbit: CameraSpec | null = null

  for (const name of Object.keys(NAMED_CAMERAS)) {
    cameraSelect.append(new Option(name, name))
    cameraEndSelect.append(new Option(name, name))
  }
  const seek = (seconds: number) => {
    const duration = context.video?.durationSeconds ?? Infinity
    context.player?.seek(Math.min(Math.max(0, seconds), duration))
  }
  scrub.addEventListener('input', () => seek(Number(scrub.value)))
  for (const button of panel.querySelectorAll<HTMLButtonElement>('[data-step]')) {
    button.addEventListener('click', () => seek(context.time() + Number(button.dataset.step)))
  }
  for (const button of panel.querySelectorAll<HTMLButtonElement>('[data-frames]')) {
    button.addEventListener('click', () => seek(context.time() + Number(button.dataset.frames) / (context.video?.fps ?? 30)))
  }
  get('mark-start').addEventListener('click', () => { start = round(context.time(), 4); startOut.value = start.toFixed(3) })
  get('mark-end').addEventListener('click', () => { end = round(context.time(), 4); endOut.value = end.toFixed(3) })
  cameraSelect.addEventListener('change', () => {
    const spec = NAMED_CAMERAS[cameraSelect.value]
    if (!spec) return
    context.explore()
    context.viewer.applyCamera(cameraPose(spec))
    context.viewer.controls.target.fromArray(spec.target)
    context.viewer.controls.update()
    context.redraw()
  })
  get('capture-end').addEventListener('click', () => {
    endOrbit = liveCamera(context.viewer)
    cameraEndSelect.value = 'orbit'
  })
  turnsStart.addEventListener('input', () => { context.explore(); context.input.crankTurns = Number(turnsStart.value); context.redraw() })
  turnsEnd.addEventListener('input', () => { context.explore(); context.input.crankTurns = Number(turnsEnd.value); context.redraw() })
  presetSelect.addEventListener('change', () => {
    const preset = context.track?.spec.presets[presetSelect.value]
    if (!preset) return
    context.explore()
    context.input.amplitudes.set(preset.amplitudes)
    context.input.phases.set(preset.phases)
    context.redraw()
  })

  function row(): Shot {
    const shot: Shot = { start, end, mode: modeSelect.value as Shot['mode'] }
    if (shot.mode === 'follow') {
      shot.camera = cameraSelect.value || liveCamera(context.viewer)
      const cameraEnd = cameraEndSelect.value === 'orbit' ? endOrbit : cameraEndSelect.value || null
      if (cameraEnd) shot.cameraEnd = cameraEnd
      shot.crankTurns = [Number(turnsStart.value), Number(turnsEnd.value)]
      shot.preset = presetSelect.value || 'zero'
      const setup = setupOf(context.input)
      if (setup) shot.setup = setup
    }
    if (unverified.checked) shot.review = 'unverified'
    return shot
  }
  get('copy').addEventListener('click', () => {
    out.value = JSON.stringify(row())
    void navigator.clipboard?.writeText(out.value)
  })
  get('current').addEventListener('click', () => {
    const track = context.track
    const index = track?.shotAt(context.time()) ?? -1
    out.value = track && index >= 0 ? JSON.stringify(track.spec.shots[index]) : 'No shot at this time.'
  })

  let presetsOf: Track | null = null
  const refresh = () => {
    const time = context.time()
    timeOut.value = `${time.toFixed(3)} s`
    scrub.max = String(context.video?.durationSeconds ?? 0)
    if (document.activeElement !== scrub) scrub.value = String(time)
    if (presetsOf !== context.track) {
      presetsOf = context.track
      presetSelect.replaceChildren(...Object.keys(presetsOf?.spec.presets ?? { zero: null }).map(name => new Option(name, name)))
    }
    requestAnimationFrame(refresh)
  }
  refresh()
}
