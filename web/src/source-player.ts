import { VideoPlayerError, type PlaybackState, type VideoAudio, type VideoPlayer, type VideoPlayerOptions } from './youtube-player'
import { VIDEOS } from './video-catalog'
import type { CompactSourceFrame } from './source-track'

export type SourceSeekIntent = 'manual' | 'reference-review'
export type SourceSeekState = 'idle' | 'seeking-idr' | 'awaiting-presentation' | 'preroll' | 'pausing'
export interface SourceAccessIndex {
  schemaVersion: 1
  kind: 'original-h264-idr-access-index'
  source: { videoId: string; sha256: string; bytes: number }
  timeBase: [number, number]
  pts: number[]
  idrPts: number[]
}
export interface SourcePresentation {
  frameIndex: number
  pts: number
  timeBase: readonly [number, number]
  mediaTime: number
  presentedFrames: number
  presentationTime: number
  currentTime: number
}
export interface SourceVideoPlayer extends VideoPlayer {
  seek(seconds: number, intent?: SourceSeekIntent): Promise<SourcePresentation>
  getSeekState(): SourceSeekState
  getSeekIntent(): SourceSeekIntent | null
  getPresentation(): SourcePresentation | null
  setVolume(volume: number): void
  setMuted(muted: boolean): void
  getMuted(): boolean
}
export function isSourceVideoPlayer(player: VideoPlayer): player is SourceVideoPlayer {
  return 'getSeekState' in player
}

function upperBound(values: readonly number[], value: number): number {
  let low = 0, high = values.length
  while (low < high) { const mid = (low + high) >>> 1; if (values[mid]! <= value) low = mid + 1; else high = mid }
  return low
}
export function sourceSeconds(index: SourceAccessIndex, pts: number): number { return pts * index.timeBase[0] / index.timeBase[1] }
/** Browser selection argument only. Integer original PTS/time_base remains the authority. */
export function browserSeekSeconds(index: SourceAccessIndex, pts: number): number {
  const denominator = BigInt(index.timeBase[1])
  const micros = (BigInt(pts) * BigInt(index.timeBase[0]) * 1_000_000n + denominator - 1n) / denominator
  if (micros > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Original PTS exceeds browser seek precision')
  return Number(micros) / 1_000_000
}
function sourceFrameIndex(index: SourceAccessIndex, seconds: number): number {
  let frameIndex = upperBound(index.pts, seconds * index.timeBase[1] / index.timeBase[0]) - 1
  // Existing decoded-time callers and rVFC may supply decimal microseconds.
  if (frameIndex + 1 < index.pts.length && Math.abs(sourceSeconds(index, index.pts[frameIndex + 1]!) - seconds) <= 1e-6) frameIndex++
  return frameIndex
}
export function selectSourceExposure(index: SourceAccessIndex, seconds: number): { frameIndex: number; pts: number; idrPts: number } {
  if (!Number.isFinite(seconds) || seconds < 0) throw new RangeError('Original seek time must be finite and nonnegative')
  const frameIndex = sourceFrameIndex(index, seconds)
  if (frameIndex < 0) throw new Error('No original source exposure at the requested time')
  const pts = index.pts[frameIndex]!, idrPts = index.idrPts[upperBound(index.idrPts, pts) - 1]
  if (idrPts === undefined) throw new Error('No verified original IDR precedes the requested exposure')
  return { frameIndex, pts, idrPts }
}
function sameOriginalValue(left: unknown, right: unknown): boolean {
  if (left === right) return true
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object') return false
  if (Array.isArray(left) !== Array.isArray(right) || Array.isArray(left) && left.length !== (right as unknown[]).length) return false
  const a = left as Record<string, unknown>, b = right as Record<string, unknown>
  for (const key in a) if (Object.hasOwn(a, key) && (!Object.hasOwn(b, key) || !sameOriginalValue(a[key], b[key]))) return false
  for (const key in b) if (Object.hasOwn(b, key) && !Object.hasOwn(a, key)) return false
  return true
}
function sameOriginalSample(left: CompactSourceFrame, right: CompactSourceFrame): boolean {
  const image = left.sourceImage, otherImage = right.sourceImage
  if (!image || !otherImage || image.frameIndex !== otherImage.frameIndex || image.sourceSha256 !== otherImage.sourceSha256
    || image.width !== otherImage.width || image.height !== otherImage.height
    || image.pixelFormat === otherImage.pixelFormat && !sameOriginalValue(image, otherImage)
    || left.decodedTimeSeconds !== null && right.decodedTimeSeconds !== null && Math.abs(left.decodedTimeSeconds - right.decodedTimeSeconds) > 1e-6) return false
  if (left.shotId !== right.shotId || left.classification !== right.classification || (left.sourceSampleUnavailable === true) !== (right.sourceSampleUnavailable === true)
    || left.views.length !== right.views.length) return false
  for (let i = 0; i < left.views.length; i++) {
    const a = left.views[i]!, b = right.views[i]!
    if (a.id !== b.id || a.presentation !== b.presentation || a.cameraInterpolation !== b.cameraInterpolation || a.cameraContinuityFamily !== b.cameraContinuityFamily
      || !sameOriginalValue(a.sourceViewIds, b.sourceViewIds) || !sameOriginalValue(a.rectSourcePixels, b.rectSourcePixels) || !sameOriginalValue(a.sourceVisibility, b.sourceVisibility)
      || !sameOriginalValue(a.camera, b.camera) || !sameOriginalValue(a.input, b.input) || !sameOriginalValue(a.sourceAssembly, b.sourceAssembly)
      || !sameOriginalValue(a.composite, b.composite) || !sameOriginalValue(a.imagePlaneWarp, b.imagePlaneWarp)) return false
  }
  return true
}
/** Bind only exact retained original exposures; aliases must describe the same pose/view policy. */
export function buildOriginalPresentationSamples(frames: readonly CompactSourceFrame[]): Map<number, number> {
  const selected = new Map<number, CompactSourceFrame>()
  for (const frame of frames) {
    if (!frame.sourceImage) continue
    const prior = selected.get(frame.sourceImage.frameIndex)
    if (prior && !sameOriginalSample(prior, frame)) throw new Error(`Original exposure ${frame.sourceImage.frameIndex} has contradictory authored pose/view aliases; source following is unavailable.`)
    // Equal semantics make the nearest retained authored key deterministic, not a pose guess.
    if (!prior || Math.abs(frame.timeSeconds - (frame.decodedTimeSeconds ?? frame.timeSeconds)) < Math.abs(prior.timeSeconds - (prior.decodedTimeSeconds ?? prior.timeSeconds))) selected.set(frame.sourceImage.frameIndex, frame)
  }
  const times = new Map<number, number>()
  for (const [index, frame] of selected) times.set(index, frame.timeSeconds)
  return times
}
export function validateSourceAccessIndex(value: unknown, videoId: string): SourceAccessIndex {
  const index = value as SourceAccessIndex, expected = VIDEOS.find(video => video.id === videoId)
  const integers = (values: unknown): values is number[] => Array.isArray(values) && values.length > 0 && values.every((n, i) => Number.isSafeInteger(n) && n >= 0 && (!i || n > values[i - 1]))
  if (!index || index.schemaVersion !== 1 || index.kind !== 'original-h264-idr-access-index' || !expected || index.source?.videoId !== videoId || index.source.sha256 !== expected.sourceSha256 || !Number.isSafeInteger(index.source.bytes) || index.source.bytes <= 0
    || !Array.isArray(index.timeBase) || index.timeBase.length !== 2 || index.timeBase.some(n => !Number.isSafeInteger(n) || n <= 0) || !integers(index.pts) || !integers(index.idrPts) || index.pts[0] !== index.idrPts[0]
    || index.idrPts.some(pts => index.pts[upperBound(index.pts, pts) - 1] !== pts)) throw new Error('Original safe-access metadata is unsupported or not bound to the retained source')
  return index
}

/** Opt-in unchanged original bytes. Unsupported access metadata refuses before playback. */
export async function createSourceVideoPlayer(container: HTMLElement, videoId: string, onState: (state: PlaybackState) => void, options: VideoPlayerOptions = {}): Promise<SourceVideoPlayer> {
  const indexDeadline = AbortSignal.timeout(20_000)
  const response = await fetch(`${import.meta.env.BASE_URL}reference-media/${encodeURIComponent(videoId)}.access.json`, { signal: options.signal ? AbortSignal.any([options.signal, indexDeadline]) : indexDeadline })
  if (!response.ok) throw new VideoPlayerError('api-load', 'Original reference safe-access index is unavailable. Prepare it before serving the original media.')
  const index = validateSourceAccessIndex(await response.json(), videoId)
  options.signal?.throwIfAborted()
  return new Promise((resolve, reject) => {
    const media = document.createElement('video')
    if (typeof media.requestVideoFrameCallback !== 'function') { reject(new VideoPlayerError('api-load', 'Original safe seeking requires actual native video presentation callbacks.')); return }
    // Built-in timelines/seek keys bypass decoder ownership; app controls use seek().
    media.controls = false
    media.playsInline = true
    media.preload = 'metadata'
    media.setAttribute('aria-label', 'Original reference video with audio')
    media.style.width = '100%'
    media.style.height = '100%'
    media.style.objectFit = 'contain'
    media.src = `${import.meta.env.BASE_URL}reference-media/${encodeURIComponent(videoId)}.mp4`
    const originalMediaUrl = media.src
    container.replaceChildren(media)
    let state: PlaybackState = 'unstarted', error: VideoPlayerError | null = null
    let ready = false, destroyed = false, playRequest = 0
    let seekState: SourceSeekState = 'idle', seekIntent: SourceSeekIntent | null = null
    let presentation: SourcePresentation | null = null
    let presentationPlayback: 'paused' | 'playing' = 'playing'
    let cancelSeek: ((cause: Error) => void) | null = null
    let trackingCallback = 0, presentationEpoch = 0, lastPresentedFrames = 0
    const stopTracking = (): void => {
      presentationEpoch++
      media.cancelVideoFrameCallback(trackingCallback)
      trackingCallback = 0
      presentation = null
      presentationPlayback = 'playing'
    }
    const startTracking = (): void => {
      if (destroyed || error || media.seeking || trackingCallback) return
      const epoch = presentationEpoch
      const started = performance.now()
      const observedFrame: VideoFrameRequestCallback = (_now, frame) => {
        if (destroyed || error || media.seeking || epoch !== presentationEpoch) return
        if (!Number.isSafeInteger(frame.presentedFrames) || frame.presentedFrames <= lastPresentedFrames || !Number.isFinite(frame.presentationTime) || frame.presentationTime < started) {
          trackingCallback = media.requestVideoFrameCallback(observedFrame)
          return
        }
        lastPresentedFrames = frame.presentedFrames
        const frameIndex = sourceFrameIndex(index, frame.mediaTime), pts = index.pts[frameIndex]
        if (pts !== undefined && Math.abs(sourceSeconds(index, pts) - frame.mediaTime) <= 1e-6) {
          presentation = { frameIndex, pts, timeBase: index.timeBase, mediaTime: frame.mediaTime, presentedFrames: frame.presentedFrames, presentationTime: frame.presentationTime, currentTime: media.currentTime }
          presentationPlayback = media.paused ? 'paused' : 'playing'
        } else presentation = null
        trackingCallback = media.requestVideoFrameCallback(observedFrame)
      }
      trackingCallback = media.requestVideoFrameCallback(observedFrame)
    }
    const audio: { state: VideoAudio['state']; volume: number } = { state: 'audible', volume: 100 }
    const publish = (next: PlaybackState): void => { if (!destroyed) { state = next; onState(next) } }
    const destroy = (): void => {
      if (destroyed) return
      cancelSeek?.(new Error('Original source seek was destroyed'))
      stopTracking()
      destroyed = true
      playRequest++
      window.clearTimeout(timeout)
      options.signal?.removeEventListener('abort', abort)
      media.pause()
      media.removeAttribute('src')
      media.load()
      media.remove()
    }
    const abort = (): void => { if (!ready) reject(new VideoPlayerError('aborted', 'Original reference video load was aborted.')); destroy() }
    const fail = (message: string): void => {
      if (destroyed) return
      error = new VideoPlayerError('api-load', message)
      cancelSeek?.(error)
      stopTracking()
      publish('error')
      options.onError?.(error)
      if (!ready) { reject(error); destroy() }
    }
    const timeout = window.setTimeout(() => fail('The original reference video did not load. Serve the preserved source MP4 at the reference-media route.'), 20_000)
    const seek = (seconds: number, intent: SourceSeekIntent = 'manual'): Promise<SourcePresentation> => {
      if (destroyed || !ready || error || media.error) return Promise.reject(new Error('Original source is unavailable for native seeking'))
      if (seekState !== 'idle') return Promise.reject(new Error('An original native seek is already active'))
      if (!Number.isFinite(seconds) || seconds < 0 || seconds > media.duration) return Promise.reject(new RangeError('Original video seek must be within its duration'))
      const target = selectSourceExposure(index, seconds), targetTime = sourceSeconds(index, target.pts)
      // A stationary, already-owned native exposure needs no decoder transaction.
      // Never infer it from clock alone or reuse a frame after playback/new ownership.
      if (presentation?.pts === target.pts && presentationPlayback === 'paused' && media.paused && !media.seeking
        && media.currentSrc === originalMediaUrl && media.src === originalMediaUrl && media.currentTime === presentation.currentTime) return Promise.resolve(presentation)
      return new Promise((resolveSeek, rejectSeek) => {
        let callback = 0, settled = false, seeked = false, observedSeeking = false
        let pendingFrame: VideoFrameCallbackMetadata | null = null
        const started = performance.now(), presentationFloor = lastPresentedFrames, deadline = started + 20_000
        seekState = 'seeking-idr'; seekIntent = intent; presentation = null
        playRequest++
        media.pause()
        const finish = (cause?: Error, frame?: VideoFrameCallbackMetadata): void => {
          if (settled) return
          settled = true
          window.clearTimeout(timer)
          media.cancelVideoFrameCallback(callback)
          media.removeEventListener('seeking', seeking)
          media.removeEventListener('seeked', didSeek)
          media.removeEventListener('ended', ended)
          media.removeEventListener('pause', paused)
          cancelSeek = null
          seekState = 'pausing'
          media.pause()
          seekState = 'idle'; seekIntent = null
          stopTracking()
          if (cause) { rejectSeek(cause); return }
          if (!frame || !media.paused || media.seeking || media.error || performance.now() >= deadline || Math.abs(media.currentTime - targetTime) > 0.5) { rejectSeek(new Error('Original target presentation did not settle with a real paused native clock')); return }
          presentation = { frameIndex: target.frameIndex, pts: target.pts, timeBase: index.timeBase, mediaTime: frame.mediaTime, presentedFrames: frame.presentedFrames, presentationTime: frame.presentationTime, currentTime: media.currentTime }
          presentationPlayback = 'paused'
          publish('paused')
          resolveSeek(presentation)
        }
        cancelSeek = cause => finish(cause)
        const timer = window.setTimeout(() => finish(new Error('Original native target presentation timed out')), 20_000)
        const acceptFrame = (frame: VideoFrameCallbackMetadata): void => {
          if (settled) return
          if (!observedSeeking) { callback = media.requestVideoFrameCallback(onFrame); return }
          if (performance.now() >= deadline) { finish(new Error('Original native target presentation timed out')); return }
          if (!Number.isSafeInteger(frame.presentedFrames) || frame.presentedFrames <= presentationFloor || !Number.isFinite(frame.presentationTime) || frame.presentationTime < started) {
            callback = media.requestVideoFrameCallback(onFrame)
            return
          }
          lastPresentedFrames = Math.max(lastPresentedFrames, frame.presentedFrames)
          if (!seeked) { pendingFrame = frame; return }
          if (Math.abs(frame.mediaTime - targetTime) <= 1e-6) finish(undefined, frame)
          else if (frame.mediaTime > targetTime + 1e-6) finish(new Error('Original native playback skipped the requested source exposure'))
          else callback = media.requestVideoFrameCallback(onFrame)
        }
        const onFrame: VideoFrameRequestCallback = (_now, frame) => acceptFrame(frame)
        const seeking = (): void => {
          if (observedSeeking) { finish(new Error('Original native seek was superseded by another timeline seek')); return }
          observedSeeking = true
        }
        const didSeek = (): void => {
          if (!observedSeeking || media.seeking || settled) return
          seeked = true
          seekState = target.pts === target.idrPts ? 'awaiting-presentation' : 'preroll'
          if (pendingFrame) { const frame = pendingFrame; pendingFrame = null; acceptFrame(frame) }
          if (!settled && seekState === 'preroll') void media.play().catch((cause: unknown) => finish(cause instanceof Error ? cause : new Error('Original native preroll playback was refused')))
        }
        const ended = (): void => finish(new Error('Original native playback ended before the requested exposure'))
        const paused = (): void => { if (seekState === 'preroll') finish(new Error('Original native preroll was paused before the requested exposure')) }
        media.addEventListener('seeking', seeking)
        media.addEventListener('seeked', didSeek)
        media.addEventListener('ended', ended)
        media.addEventListener('pause', paused)
        callback = media.requestVideoFrameCallback(onFrame)
        // Never seek to the target GOP and retry. The only seek is the verified IDR.
        try { media.currentTime = browserSeekSeconds(index, target.idrPts) }
        catch (cause) { finish(cause instanceof Error ? cause : new Error('Original IDR seek was refused')) }
      })
    }
    media.addEventListener('loadedmetadata', () => {
      if (destroyed || ready) return
      if (!Number.isFinite(media.duration) || media.duration <= 0) { fail('The original reference video has no usable duration.'); return }
      ready = true
      window.clearTimeout(timeout)
      startTracking()
      publish('paused')
      resolve({
        getTime: () => media.currentTime,
        getVideoId: () => ready && !destroyed ? decodeURIComponent(new URL(media.currentSrc).pathname.split('/').at(-1) ?? '').replace(/\.mp4$/, '') : null,
        getState: () => destroyed || state === 'error' ? 'error' : media.ended ? 'ended' : media.paused ? 'paused' : state,
        getSeekState: () => seekState,
        getSeekIntent: () => seekIntent,
        getPresentation: () => destroyed || error || media.seeking || seekState !== 'idle' || media.currentSrc !== originalMediaUrl || media.src !== originalMediaUrl ? null : presentation,
        play: () => {
          if (cancelSeek) cancelSeek(new Error('Original native seek was superseded by playback'))
          presentationPlayback = 'playing'
          startTracking()
          const request = ++playRequest
          void media.play().catch((cause: unknown) => {
            if (destroyed || request !== playRequest) return
            if (cause instanceof Error && cause.name === 'AbortError') { if (media.paused) publish('paused'); return }
            if (cause instanceof Error && cause.name === 'NotAllowedError') {
              publish('paused')
              options.onError?.(new VideoPlayerError('autoplay-blocked', 'Original video playback was blocked. Press Play in the video controls to continue.'))
              return
            }
            fail(cause instanceof Error ? cause.message : 'Original video playback was refused.')
          })
        },
        pause: () => { cancelSeek?.(new Error('Original native seek was cancelled by pause')); playRequest++; media.pause() },
        seek,
        setVolume: (volume: number) => { if (!Number.isFinite(volume) || volume < 0 || volume > 100) throw new RangeError('Original volume must be between 0 and 100'); media.volume = volume / 100 },
        setMuted: (muted: boolean) => { media.muted = muted },
        getMuted: () => media.muted,
        getAudio: () => { audio.state = media.muted || media.volume === 0 ? 'muted' : 'audible'; audio.volume = media.volume * 100; return audio },
        getError: () => error,
        destroy,
      })
    })
    media.addEventListener('playing', () => { if (!media.paused) { presentationPlayback = 'playing'; startTracking() } if (!error) publish(media.paused ? 'paused' : 'playing') })
    media.addEventListener('waiting', () => { if (!media.paused) publish('buffering') })
    media.addEventListener('pause', () => { playRequest++; if (!media.ended && !error) publish('paused') })
    media.addEventListener('ended', () => publish('ended'))
    media.addEventListener('seeking', stopTracking)
    media.addEventListener('seeked', () => {
      if (destroyed || !ready || media.seeking || state === 'error') return
      startTracking()
      const next = media.ended ? 'ended' : media.paused ? 'paused' : media.readyState < media.HAVE_FUTURE_DATA ? 'buffering' : 'playing'
      if (next !== state) publish(next)
    })
    media.addEventListener('error', () => fail(`Original reference video load failed (${media.error?.message ?? 'media unavailable'}).`))
    if (options.signal?.aborted) abort()
    else options.signal?.addEventListener('abort', abort, { once: true })
  })
}
