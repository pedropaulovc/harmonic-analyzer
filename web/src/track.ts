/**
 * Shot tables: what the 3D companion shows while each video plays.
 *
 * content/tracks/<slug>.json lists contiguous shots; content/cameras.json names
 * reusable cameras. A "follow" shot interpolates linearly from its start to its
 * end values (camera position lerp, orientation slerp, crank turns, preset
 * amplitudes and shortest-path phases, setupEnd fields). A "hold" shot freezes
 * the previous follow shot's end state (or the next one's start). Tiles split
 * the 1920x1080 video frame into several views; each tile inherits every field
 * it does not override from its shot. Rows marked "review": "unverified" were
 * roughed in and have not been checked against the footage.
 */
import * as THREE from 'three'
import cameras from '../content/cameras.json'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { MAGNIFIER_RATIO_BUILT, MAGNIFIER_RATIO_MAX, MAGNIFIER_RATIO_MIN, type Gearing } from './kinematics'

export type Vec3 = [number, number, number]
export type Rect = [number, number, number, number]
export interface CameraSpec { position: Vec3; target: Vec3; up?: Vec3; fov: number; principal?: [number, number] }
export type CameraRef = string | CameraSpec
type NumericSetupKey = 'magnification' | keyof MechanismInput['setup']
export interface SetupSpec extends Partial<Record<NumericSetupKey, number>> { gearing?: Gearing }
export interface ShotFields {
  camera?: CameraRef
  cameraEnd?: CameraRef
  crankTurns?: [number, number]
  preset?: string
  presetEnd?: string
  setup?: SetupSpec
  setupEnd?: Partial<Record<NumericSetupKey, number>>
}
export interface TileSpec extends ShotFields { rect?: Rect; mirror?: boolean }
export interface Shot extends ShotFields {
  start: number
  end: number
  mode: 'follow' | 'hold'
  tiles?: TileSpec[]
  review?: 'unverified'
  note?: string
}
export interface Preset { amplitudes: number[]; phases: number[] }
export interface TrackSpec { video: string; presets: Record<string, Preset>; shots: Shot[] }

/** A resolved camera: what the viewer renders. principal is a fraction of the tile. */
export interface CameraPose { position: THREE.Vector3; quaternion: THREE.Quaternion; fov: number; principal: THREE.Vector2 }
export interface TrackView { rect: Rect; mirror: boolean; camera: CameraPose; input: MechanismInput }

interface Tile {
  rect: Rect
  mirror: boolean
  camera: CameraPose
  cameraEnd: CameraPose | null
  crankTurns: [number, number]
  preset: Preset
  presetEnd: Preset | null
  setup: SetupSpec
  setupEnd: Partial<Record<NumericSetupKey, number>>
}
interface CompiledShot { start: number; end: number; tiles: Tile[] | null; holdOf: { shot: number; fraction: number } | null }

export const FULL_FRAME: Rect = [0, 0, 1920, 1080]
export const NAMED_CAMERAS = cameras as unknown as Record<string, CameraSpec>
const FORWARD = new THREE.Vector3()
const UP = new THREE.Vector3()
const RIGHT = new THREE.Vector3()
const BASIS = new THREE.Matrix4()

export function cameraPose(spec: CameraSpec, out: CameraPose = createCameraPose()): CameraPose {
  out.position.fromArray(spec.position)
  FORWARD.fromArray(spec.target).sub(out.position).normalize()
  UP.fromArray(spec.up ?? [0, 1, 0])
  RIGHT.crossVectors(FORWARD, UP).normalize()
  UP.crossVectors(RIGHT, FORWARD)
  BASIS.makeBasis(RIGHT, UP, FORWARD.negate())
  out.quaternion.setFromRotationMatrix(BASIS)
  out.fov = spec.fov
  out.principal.fromArray(spec.principal ?? [0.5, 0.5])
  return out
}

export function createCameraPose(): CameraPose {
  return { position: new THREE.Vector3(), quaternion: new THREE.Quaternion(), fov: 30, principal: new THREE.Vector2(0.5, 0.5) }
}

function resolveCamera(ref: CameraRef | undefined, where: string): CameraPose {
  const spec = typeof ref === 'string' ? NAMED_CAMERAS[ref] : ref
  if (!spec) throw new Error(`${where}: unknown camera ${JSON.stringify(ref)}`)
  return cameraPose(spec)
}

function phaseDelta(a: number, b: number): number {
  const turn = 2 * Math.PI
  let d = (((b % turn) - (a % turn)) % turn + turn) % turn
  if (d >= Math.PI) d -= turn
  return d
}

export class Track {
  readonly shots: CompiledShot[]
  private readonly views: TrackView[] = []

  constructor(readonly spec: TrackSpec) {
    const preset = (name: string | undefined, where: string): Preset => {
      const found = name === undefined ? undefined : spec.presets[name]
      if (!found) throw new Error(`${where}: unknown preset ${JSON.stringify(name)}`)
      return found
    }
    this.shots = spec.shots.map((shot, index) => {
      const where = `${spec.video} shot ${index} (${shot.start}s)`
      if (shot.mode === 'hold') return { start: shot.start, end: shot.end, tiles: null, holdOf: null }
      const tiles = (shot.tiles ?? [{}]).map((tile): Tile => {
        const get = <K extends keyof ShotFields>(key: K): ShotFields[K] => tile[key] ?? shot[key]
        const presetEnd = get('presetEnd')
        const cameraEnd = get('cameraEnd')
        return {
          rect: tile.rect ?? FULL_FRAME,
          mirror: tile.mirror ?? false,
          camera: resolveCamera(get('camera'), where),
          cameraEnd: cameraEnd === undefined ? null : resolveCamera(cameraEnd, where),
          crankTurns: get('crankTurns') ?? [0, 0],
          preset: preset(get('preset') ?? 'zero', where),
          presetEnd: presetEnd === undefined ? null : preset(presetEnd, where),
          setup: get('setup') ?? {},
          setupEnd: get('setupEnd') ?? {},
        }
      })
      for (let i = this.views.length; i < tiles.length; i++) {
        this.views.push({ rect: FULL_FRAME, mirror: false, camera: createCameraPose(), input: createMechanismInput() })
      }
      return { start: shot.start, end: shot.end, tiles, holdOf: null }
    })
    // A hold shows the previous follow shot's end, or the first one's start.
    let previous = -1
    for (let i = 0; i < this.shots.length; i++) {
      const shot = this.shots[i]!
      if (shot.tiles) previous = i
      else if (previous >= 0) shot.holdOf = { shot: previous, fraction: 1 }
    }
    const first = this.shots.findIndex(shot => shot.tiles)
    for (const shot of this.shots) if (!shot.tiles && !shot.holdOf && first >= 0) shot.holdOf = { shot: first, fraction: 0 }
  }

  /** The shot index active at a time, or -1 outside every shot. */
  shotAt(time: number): number {
    let lo = 0, hi = this.shots.length - 1, found = -1
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      if (this.shots[mid]!.start <= time) { found = mid; lo = mid + 1 } else hi = mid - 1
    }
    return found >= 0 && time < this.shots[found]!.end ? found : -1
  }

  /** Views at a time. The returned array and its objects are reused by the next call. */
  evaluate(time: number): readonly TrackView[] {
    let index = this.shotAt(time)
    if (index < 0) return []
    let shot = this.shots[index]!
    let fraction = (time - shot.start) / (shot.end - shot.start)
    if (shot.holdOf) {
      fraction = shot.holdOf.fraction
      index = shot.holdOf.shot
      shot = this.shots[index]!
    }
    const tiles = shot.tiles
    if (!tiles) return []
    for (let i = 0; i < tiles.length; i++) evaluateTile(tiles[i]!, fraction, this.views[i]!)
    return this.views.slice(0, tiles.length)
  }
}

function evaluateTile(tile: Tile, f: number, out: TrackView) {
  out.rect = tile.rect
  out.mirror = tile.mirror
  const camera = out.camera
  camera.position.copy(tile.camera.position)
  camera.quaternion.copy(tile.camera.quaternion)
  camera.fov = tile.camera.fov
  camera.principal.copy(tile.camera.principal)
  if (tile.cameraEnd) {
    camera.position.lerp(tile.cameraEnd.position, f)
    camera.quaternion.slerp(tile.cameraEnd.quaternion, f)
    camera.fov += (tile.cameraEnd.fov - camera.fov) * f
    camera.principal.lerp(tile.cameraEnd.principal, f)
  }
  const input = out.input
  input.crankTurns = tile.crankTurns[0] + (tile.crankTurns[1] - tile.crankTurns[0]) * f
  const end = tile.presetEnd
  for (let i = 0; i < input.amplitudes.length; i++) {
    const amplitude = tile.preset.amplitudes[i]!, phase = tile.preset.phases[i]!
    input.amplitudes[i] = end ? amplitude + (end.amplitudes[i]! - amplitude) * f : amplitude
    input.phases[i] = end ? phase + phaseDelta(phase, end.phases[i]!) * f : phase
  }
  const setup = tile.setup
  input.gearing = setup.gearing ?? 'small-large'
  input.magnification = setup.magnification ?? MAGNIFIER_RATIO_BUILT
  const s = input.setup
  s.counterHeightM = setup.counterHeightM ?? null
  s.meanLineAngleRad = setup.meanLineAngleRad ?? 0
  s.platenOffsetM = setup.platenOffsetM ?? 0
  s.wireFixtureOffsetM = setup.wireFixtureOffsetM ?? 0
  s.coneSwingRad = setup.coneSwingRad ?? 0
  s.pinionCamRad = setup.pinionCamRad ?? 0
  s.heldChannelTurns = setup.heldChannelTurns ?? 0
  s.driveCrankOffsetTurns = setup.driveCrankOffsetTurns ?? 0
  for (const key in tile.setupEnd) {
    const target = tile.setupEnd[key as NumericSetupKey]!
    if (key === 'magnification') input.magnification += (target - input.magnification) * f
    else {
      const name = key as keyof typeof s
      const base = s[name] ?? 0
      ;(s as Record<string, number | null>)[name] = base + (target - base) * f
    }
  }
  // Rows are hand-rounded and may predate a CAD change in travel; a setting at
  // or past an end stop means "at the stop".
  input.magnification = clamp(input.magnification, MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_MAX)
  const range = MECHANISM_DATA.magnifier.fixtureOffsetRangeM
  s.wireFixtureOffsetM = clamp(s.wireFixtureOffsetM, range[0], range[1])
  s.coneSwingRad = clamp(s.coneSwingRad, 0, MECHANISM_DATA.setup.coneDisengageRad)
  s.pinionCamRad = clamp(s.pinionCamRad, MECHANISM_DATA.setup.pinionEngageCamRad, 0)
}

function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value))
}

const sources = import.meta.glob<{ default: TrackSpec }>('../content/tracks/*.json')

/** Load the shot table for a video slug, or null if the video has none. */
export async function loadTrack(slug: string): Promise<Track | null> {
  const load = sources[`../content/tracks/${slug}.json`]
  return load ? new Track((await load()).default) : null
}
