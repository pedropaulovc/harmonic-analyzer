import { Quaternion } from 'three'
import { createMechanismInput, type MechanismInput, type SerializedMechanismInput } from './mechanics'
import type { CameraRecord, Presentation } from './scene'

export type SegmentInput = Omit<SerializedMechanismInput, 'crankTurns'>
export type SegmentInit = Omit<Partial<SegmentInput>, 'setup'> & { setup?: Partial<MechanismInput['setup']> }
export interface SyncCameraKey { t: number; camera: CameraRecord }
export interface SyncView {
  viewId: string
  rectSourcePixels: [number, number, number, number]
  presentation: Presentation
  cameraKeys: SyncCameraKey[]
  quality: { medianPx: number | null; p90Px: number | null; maxPx: number | null; status: 'fitted' | 'manual' | 'unfitted' }
}
export interface SyncShot {
  id: string
  driverViewId?: string
  start: number
  end: number
  startFrame: number
  endFrame: number
  classification: 'machine' | 'transition' | 'non-machine'
  views: SyncView[]
}
export interface SyncSegment {
  id: string
  start: number
  end: number
  input: SegmentInput
  provenance: Record<string, 'fitted' | 'chosen' | 'manual'>
}
export interface SyncTrackData {
  schemaVersion: 1
  videoId: string
  fps: [number, number]
  sourceSha256: string
  modelSha256: string
  shots: SyncShot[]
  segments: SyncSegment[]
  crank: { t: number; turns: number; source: 'tracked' | 'inferred' | 'held' }[]
}
export interface EvaluatedSyncView {
  viewId: string
  rect: readonly [number, number, number, number]
  presentation: Presentation
  camera: CameraRecord
}
export interface EvaluatedSync { views: EvaluatedSyncView[]; input: MechanismInput }
export interface SyncTrack {
  readonly data: SyncTrackData
  /** The result and its buffers are reused; copy it if retaining a past frame. */
  evaluate(t: number): EvaluatedSync
}

export function serializeSyncInput(input: MechanismInput): SerializedMechanismInput {
  return { crankTurns: input.crankTurns, amplitudes: Array.from(input.amplitudes), phases: Array.from(input.phases), gearing: input.gearing, magnification: input.magnification, setup: { ...input.setup } }
}

export function applySegmentInput(target: MechanismInput, source: SegmentInit): void {
  if (source.amplitudes) target.amplitudes.set(source.amplitudes)
  if (source.phases) target.phases.set(source.phases)
  if (source.gearing !== undefined) target.gearing = source.gearing
  if (source.magnification !== undefined) target.magnification = source.magnification
  if (source.setup) Object.assign(target.setup, source.setup)
}

/** Half-open integer-frame intervals: a cut belongs to the incoming interval. */
export function frameIntervalAt<T extends { startFrame: number; endFrame: number }>(items: readonly T[], frame: number): T | undefined {
  return items.find(item => frame >= item.startFrame && frame < item.endFrame)
}

export function createSyncTrack(data: SyncTrackData): SyncTrack {
  if (data.schemaVersion !== 1 || !data.videoId || !Array.isArray(data.fps) || data.fps.length !== 2 || !data.fps.every(value => Number.isSafeInteger(value) && value > 0) || !Array.isArray(data.shots) || !Array.isArray(data.segments) || !Array.isArray(data.crank)) throw new Error('Invalid sync track')
  const fps = data.fps[0] / data.fps[1]
  const shots = [...data.shots].sort((a, b) => a.startFrame - b.startFrame)
  const segments = data.segments.map(segment => ({ segment, startFrame: Math.round(segment.start * fps), endFrame: Math.round(segment.end * fps) })).sort((a, b) => a.startFrame - b.startFrame)
  const crank = [...data.crank].sort((a, b) => a.t - b.t)
  const input = createMechanismInput()
  const defaults = serializeSyncInput(createMechanismInput())
  const result: EvaluatedSync = { views: [], input }
  const q0 = new Quaternion(), q1 = new Quaternion()
  const buffers = new Map<SyncShot, { source: SyncView; keys: SyncCameraKey[]; output: EvaluatedSyncView }[]>()
  for (const shot of shots) {
    if (!Number.isSafeInteger(shot.startFrame) || !Number.isSafeInteger(shot.endFrame) || shot.endFrame <= shot.startFrame) throw new Error(`Invalid sync shot ${shot.id}`)
    buffers.set(shot, shot.views.filter(view => view.cameraKeys.length > 0).map(source => ({
      source, keys: [...source.cameraKeys].sort((a, b) => a.t - b.t),
      output: { viewId: source.viewId, rect: source.rectSourcePixels, presentation: source.presentation,
        camera: { positionMetres: [0, 0, 0], quaternion: [0, 0, 0, 1], verticalFovDegrees: 35, principalPointViewportPixels: [source.rectSourcePixels[2] / 2, source.rectSourcePixels[3] / 2] } },
    })))
  }
  let previousSegment: SyncSegment | undefined
  let previousShot: SyncShot | undefined

  function evaluate(t: number): EvaluatedSync {
    if (!Number.isFinite(t)) throw new Error('Sync time must be finite')
    const frame = Math.round(t * fps)
    let shot = frameIntervalAt(shots, frame)
    let poseTime = t
    let poseFrame = frame
    if (!shot || shot.classification !== 'machine') {
      shot = undefined
      for (const candidate of shots) {
        if (candidate.startFrame > frame) break
        if (candidate.classification === 'machine') shot = candidate
      }
      if (shot) {
        poseFrame = shot.endFrame - 1
        poseTime = poseFrame * data.fps[1] / data.fps[0]
      }
    }
    const segment = shot ? frameIntervalAt(segments, poseFrame)?.segment : undefined
    if (segment !== previousSegment) {
      const source = segment?.input ?? defaults
      applySegmentInput(input, source)
      previousSegment = segment
    }
    if (shot && crank.length) {
      let index = 0
      while (index + 1 < crank.length && crank[index + 1]!.t <= poseTime) index++
      const a = crank[index]!, b = crank[index + 1]
      const f = b ? Math.max(0, Math.min(1, (poseTime - a.t) / (b.t - a.t))) : 0
      input.crankTurns = b ? a.turns + (b.turns - a.turns) * f : a.turns
    } else input.crankTurns = 0
    if (!shot) {
      result.views.length = 0
      previousShot = undefined
      return result
    }
    const views = buffers.get(shot)!
    if (shot !== previousShot) {
      result.views.length = 0
      for (const view of views) result.views.push(view.output)
      previousShot = shot
    }
    for (const { source, keys, output } of views) {
      let index = 0
      while (index + 1 < keys.length && keys[index + 1]!.t <= poseTime) index++
      const a = keys[index]!, b = keys[index + 1] ?? a
      const f = b.t > a.t ? Math.max(0, Math.min(1, (poseTime - a.t) / (b.t - a.t))) : 0
      const position = output.camera.positionMetres as [number, number, number]
      for (let k = 0; k < 3; k++) position[k] = a.camera.positionMetres[k]! + (b.camera.positionMetres[k]! - a.camera.positionMetres[k]!) * f
      q0.fromArray(a.camera.quaternion).normalize().slerp(q1.fromArray(b.camera.quaternion).normalize(), f)
      q0.toArray(output.camera.quaternion as [number, number, number, number])
      output.camera.verticalFovDegrees = a.camera.verticalFovDegrees + (b.camera.verticalFovDegrees - a.camera.verticalFovDegrees) * f
      const pp = output.camera.principalPointViewportPixels as [number, number]
      for (let k = 0; k < 2; k++) {
        const centre = source.rectSourcePixels[k + 2]! / 2
        const x = a.camera.principalPointViewportPixels?.[k] ?? centre
        pp[k] = x + ((b.camera.principalPointViewportPixels?.[k] ?? centre) - x) * f
      }
    }
    return result
  }
  return { data, evaluate }
}

// Lazy URLs keep tracks out of the main app bundle and absent-video paths intact.
const urls = import.meta.glob('../content/sync/*.sync.json', { query: '?url', import: 'default' })
export async function loadSyncTrack(videoId: string, signal?: AbortSignal): Promise<SyncTrack | null> {
  const loader = urls[`../content/sync/${videoId}.sync.json`]
  if (!loader) return null
  const url = await loader() as string
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`Unable to load sync track (${response.status})`)
  const data = await response.json() as SyncTrackData
  if (data.videoId !== videoId) throw new Error('Sync track video ID differs from the selected video')
  return createSyncTrack(data)
}
