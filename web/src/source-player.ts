import { VideoPlayerError, type PlaybackState, type VideoAudio, type VideoPlayer, type VideoPlayerOptions } from './youtube-player'

/** Opt-in local playback of the retained, unchanged original MP4; never a simulated player. */
export function createSourceVideoPlayer(container: HTMLElement, videoId: string, onState: (state: PlaybackState) => void, options: VideoPlayerOptions = {}): Promise<VideoPlayer> {
  return new Promise((resolve, reject) => {
    const media = document.createElement('video')
    media.controls = true
    media.playsInline = true
    media.preload = 'metadata'
    media.setAttribute('aria-label', 'Original reference video with audio')
    media.style.width = '100%'
    media.style.height = '100%'
    media.style.objectFit = 'contain'
    media.src = `${import.meta.env.BASE_URL}reference-media/${encodeURIComponent(videoId)}.mp4`
    container.replaceChildren(media)
    let state: PlaybackState = 'unstarted'
    let error: VideoPlayerError | null = null
    let ready = false
    let destroyed = false
    let playRequest = 0
    const audio: { state: VideoAudio['state']; volume: number } = { state: 'audible', volume: 100 }
    const abort = (): void => {
      if (!ready) reject(new VideoPlayerError('aborted', 'Original reference video load was aborted.'))
      destroy()
    }
    const publish = (next: PlaybackState): void => {
      if (destroyed) return
      state = next
      onState(next)
    }
    const destroy = (): void => {
      if (destroyed) return
      destroyed = true
      playRequest++
      window.clearTimeout(timeout)
      options.signal?.removeEventListener('abort', abort)
      media.pause()
      media.removeAttribute('src')
      media.load()
      media.remove()
    }
    const fail = (message: string): void => {
      if (destroyed) return
      error = new VideoPlayerError('api-load', message)
      publish('error')
      options.onError?.(error)
      if (!ready) { reject(error); destroy() }
    }
    const timeout = window.setTimeout(() => fail('The original reference video did not load. Serve the preserved source MP4 at the reference-media route.'), 20_000)
    media.addEventListener('loadedmetadata', () => {
      if (destroyed || ready) return
      if (!Number.isFinite(media.duration) || media.duration <= 0) { fail('The original reference video has no usable duration.'); return }
      ready = true
      window.clearTimeout(timeout)
      publish('paused')
      resolve({
        getTime: () => media.currentTime,
        getVideoId: () => ready && !destroyed ? decodeURIComponent(new URL(media.currentSrc).pathname.split('/').at(-1) ?? '').replace(/\.mp4$/, '') : null,
        getState: () => destroyed ? 'error' : media.ended ? 'ended' : media.paused && state !== 'error' ? 'paused' : state,
        play: () => {
          const request = ++playRequest
          void media.play().catch((cause: unknown) => {
            if (destroyed || request !== playRequest) return
            if (cause instanceof Error && cause.name === 'AbortError') {
              error = null
              if (media.paused) publish('paused')
              return
            }
            if (cause instanceof Error && cause.name === 'NotAllowedError') {
              error = null
              publish('paused')
              options.onError?.(new VideoPlayerError('autoplay-blocked', 'Original video playback was blocked. Press Play in the video controls to continue.'))
              return
            }
            fail(cause instanceof Error ? cause.message : 'Original video playback was refused.')
          })
        },
        pause: () => { playRequest++; media.pause() },
        seek: (seconds: number) => {
          if (!Number.isFinite(seconds) || seconds < 0 || seconds > media.duration) throw new RangeError('Original video seek must be within its duration.')
          media.currentTime = seconds
        },
        getAudio: () => {
          audio.state = media.muted || media.volume === 0 ? 'muted' : 'audible'
          audio.volume = media.volume * 100
          return audio
        },
        getError: () => error,
        destroy,
      })
    })
    media.addEventListener('playing', () => {
      error = null
      publish(media.paused ? 'paused' : 'playing')
    })
    media.addEventListener('waiting', () => { if (!media.paused) publish('buffering') })
    media.addEventListener('pause', () => { playRequest++; if (!media.ended) publish('paused') })
    media.addEventListener('ended', () => publish('ended'))
    media.addEventListener('seeked', () => {
      if (destroyed || !ready || media.seeking || state === 'error') return
      // Seeking away from EOF need not emit pause again; publish the settled native state.
      publish(media.ended ? 'ended' : media.paused ? 'paused' : media.readyState < media.HAVE_FUTURE_DATA ? 'buffering' : 'playing')
    })
    media.addEventListener('error', () => fail(`Original reference video load failed (${media.error?.message ?? 'media unavailable'}).`))
    if (options.signal?.aborted) abort()
    else options.signal?.addEventListener('abort', abort, { once: true })
  })
}
