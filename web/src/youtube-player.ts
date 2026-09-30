export type PlaybackState = 'unstarted' | 'cued' | 'playing' | 'paused' | 'buffering' | 'ended' | 'error';
export type AudioState = 'muted' | 'audible';
export interface VideoAudio {
  readonly state: AudioState;
  readonly volume: number;
}
export type VideoPlayerErrorCode = 'invalid-video-id' | 'invalid-container' | 'invalid-origin' | 'api-load' | 'ready-timeout' | 'youtube' | 'autoplay-blocked' | 'replaced' | 'aborted';

export class VideoPlayerError extends Error {
  constructor(readonly code: VideoPlayerErrorCode, message: string, readonly youtubeCode?: number) {
    super(message);
    this.name = 'VideoPlayerError';
  }
}

export interface VideoPlayer {
  getTime(): number;
  /** Native currently loaded video identity, never the requested route/iframe ID. */
  getVideoId(): string | null;
  getState(): PlaybackState;
  play(): void;
  pause(): void;
  seek(seconds: number): void;
  /** A reused read-only snapshot; volume uses YouTube's 0–100 scale. */
  getAudio(): VideoAudio;
  getError(): VideoPlayerError | null;
  destroy(): void;
}
export interface VideoPlayerOptions {
  /** Includes errors after readiness; render the message visibly near the player. */
  onError?: (error: VideoPlayerError) => void;
  /** Cancels pending creation or destroys a ready player. */
  signal?: AbortSignal;
}

interface YouTubePlayer {
  getCurrentTime(): number;
  getVideoUrl(): string;
  getPlayerState(): number;
  getVolume(): number;
  isMuted(): boolean;
  playVideo(): void;
  pauseVideo(): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  destroy(): void;
}
interface YouTubeEvent { target: YouTubePlayer }
interface YouTubeOptions {
  events: {
    onReady(event: YouTubeEvent): void;
    onStateChange(event: YouTubeEvent & { data: number }): void;
    onError(event: YouTubeEvent & { data: number }): void;
    onAutoplayBlocked(event: YouTubeEvent): void;
  };
}
interface YouTubeApi { Player: new (element: HTMLElement, options: YouTubeOptions) => YouTubePlayer }
type YouTubeWindow = Window & {
  YT?: YouTubeApi;
  onYouTubeIframeAPIReady?: () => void;
};

const API_URL = 'https://www.youtube.com/iframe_api';
const LOAD_TIMEOUT_MS = 20_000;
const READY_TIMEOUT_MS = 20_000;
const loaders = new WeakMap<Window, Promise<YouTubeApi>>();
const failedScripts = new WeakSet<HTMLScriptElement>();
const occupants = new WeakMap<HTMLElement, { cancel(error: VideoPlayerError): void }>();

function hasApi(window: YouTubeWindow): boolean {
  return typeof window.YT?.Player === 'function';
}

/** One in-flight loader per browsing context, shared by all player instances. */
function loadApi(window: YouTubeWindow): Promise<YouTubeApi> {
  if (hasApi(window)) return Promise.resolve(window.YT!);
  const pending = loaders.get(window);
  if (pending) return pending;
  const promise = new Promise<YouTubeApi>((resolve, reject) => {
    const document = window.document;
    const previous = window.onYouTubeIframeAPIReady;
    let settled = false;
    let script: HTMLScriptElement | undefined;
    let ownedScript = false;
    let timeout: number | undefined;
    const cleanup = () => {
      window.clearTimeout(timeout);
      script?.removeEventListener('error', failed);
      script?.removeEventListener('load', loaded);
      // Do not overwrite a callback installed by somebody else while loading.
      if (window.onYouTubeIframeAPIReady === ready) {
        if (previous) window.onYouTubeIframeAPIReady = previous;
        else delete window.onYouTubeIframeAPIReady;
      }
    };
    const finish = (error?: VideoPlayerError) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (error) {
        if (script) failedScripts.add(script);
        if (ownedScript) script?.remove();
        reject(error);
      } else resolve(window.YT!);
    };
    const ready = () => {
      try { previous?.call(window); }
      finally {
        if (hasApi(window)) finish();
        else finish(new VideoPlayerError('api-load', 'YouTube API announced readiness without a player constructor.'));
      }
    };
    const failed = () => finish(new VideoPlayerError('api-load', 'YouTube API could not load. Check network access, content blockers and the page content-security policy.'));
    const loaded = () => { if (hasApi(window)) finish(); };
    window.onYouTubeIframeAPIReady = ready;
    for (const candidate of document.scripts) {
      if (candidate.src === API_URL && !failedScripts.has(candidate)) { script = candidate; break; }
    }
    if (!script) {
      script = document.createElement('script');
      script.src = API_URL;
      script.async = true;
      script.referrerPolicy = 'strict-origin-when-cross-origin';
      ownedScript = true;
    }
    script.addEventListener('error', failed);
    script.addEventListener('load', loaded);
    timeout = window.setTimeout(() => finish(new VideoPlayerError('api-load', 'Timed out loading the YouTube player API. Check network access and content blockers.')), LOAD_TIMEOUT_MS);
    if (ownedScript) {
      try { document.head.append(script); }
      catch { failed(); }
    }
  });
  loaders.set(window, promise);
  // Failed loads may be retried; successful loads are also detected directly above.
  void promise.catch(() => { if (loaders.get(window) === promise) loaders.delete(window); });
  return promise;
}

function decodeState(state: number): PlaybackState {
  switch (state) {
    case -1: return 'unstarted';
    case 0: return 'ended';
    case 1: return 'playing';
    case 2: return 'paused';
    case 3: return 'buffering';
    case 5: return 'cued';
    default: return 'unstarted';
  }
}

function youtubeError(code: number): VideoPlayerError {
  let message: string;
  switch (code) {
    case 2: message = 'YouTube rejected the video identifier or playback parameters.'; break;
    case 5: message = 'YouTube cannot play this video in this browser using the HTML5 player.'; break;
    case 100: message = 'This YouTube video is unavailable, removed or private.'; break;
    case 101:
    case 150: message = 'The owner of this video does not permit embedded playback. Open it on YouTube.'; break;
    case 153: message = 'YouTube rejected the embed because its HTTP referrer or client identity is missing. Allow the page origin as a referrer.'; break;
    default: message = `YouTube playback failed (code ${code}). The video may require authentication or be restricted in your region; open it on YouTube.`;
  }
  return new VideoPlayerError('youtube', message, code);
}

/**
 * Creates a visible, user-controlled YouTube embed. Resolves only on actual
 * onReady, never on script load. A new instance in the same container cancels
 * its predecessor; callers can also abort pending creation with options.signal.
 */
export function createVideoPlayer(
  container: HTMLElement,
  videoId: string,
  onState: (state: PlaybackState) => void,
  options: VideoPlayerOptions = {},
): Promise<VideoPlayer> {
  if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
    return Promise.reject(new VideoPlayerError('invalid-video-id', 'A YouTube video ID must contain exactly 11 letters, numbers, underscores or hyphens.'));
  }
  const window = container.ownerDocument.defaultView as YouTubeWindow | null;
  if (!window || !container.isConnected) {
    return Promise.reject(new VideoPlayerError('invalid-container', 'Attach the player container to a live document before creating the player.'));
  }
  if (!/^https?:$/.test(window.location.protocol)) {
    return Promise.reject(new VideoPlayerError('invalid-origin', 'YouTube playback requires an HTTP or HTTPS page origin, not a local file.'));
  }
  if (options.signal?.aborted) return Promise.reject(new VideoPlayerError('aborted', 'Player creation was cancelled.'));
  occupants.get(container)?.cancel(new VideoPlayerError('replaced', 'This player was replaced by another video in the same container.'));

  return new Promise<VideoPlayer>((resolve, reject) => {
    let raw: YouTubePlayer | undefined;
    let iframe: HTMLIFrameElement | undefined;
    let disposed = false;
    let ready = false;
    let settled = false;
    let timer: number | undefined;
    let state: PlaybackState = 'unstarted';
    let time = 0;
    let lastError: VideoPlayerError | null = null;
    const audio: { state: AudioState; volume: number } = { state: 'muted', volume: 0 };
    const notify = <T>(callback: ((value: T) => void) | undefined, value: T) => {
      try { callback?.(value); }
      catch (error) { console.error('YouTube player consumer callback failed:', error); }
    };
    const active = () => !disposed && occupants.get(container) === owner;
    const publish = (next: PlaybackState) => {
      if (!active()) return;
      state = next;
      notify(onState, next);
    };
    const destroy = () => {
      if (disposed) return;
      if (ready && raw) {
        time = readTime();
      }
      disposed = true;
      state = 'unstarted';
      audio.state = 'muted';
      audio.volume = 0;
      window.clearTimeout(timer);
      options.signal?.removeEventListener('abort', aborted);
      if (occupants.get(container) === owner) occupants.delete(container);
      try { raw?.destroy(); }
      finally { iframe?.remove(); }
    };
    const fail = (error: VideoPlayerError) => {
      if (!active()) return;
      lastError = error;
      publish('error');
      if (!active()) return;
      notify(options.onError, error);
      if (!settled) {
        settled = true;
        reject(error);
        destroy();
      }
      // Once ready, retain the visible YouTube error UI and permit user retry.
    };
    const cancel = (error: VideoPlayerError) => {
      if (!settled) { settled = true; reject(error); }
      destroy();
    };
    const owner = { cancel };
    const aborted = () => cancel(new VideoPlayerError('aborted', 'Player creation or playback was cancelled.'));
    occupants.set(container, owner);
    options.signal?.addEventListener('abort', aborted, { once: true });
    const readTime = () => {
      if (ready && !disposed && raw) {
        const value = raw.getCurrentTime();
        if (Number.isFinite(value) && value >= 0) time = value;
      }
      return time;
    };
    const readAudio = (): VideoAudio => {
      if (ready && !disposed && raw) {
        const volume = raw.getVolume();
        audio.volume = Number.isFinite(volume) ? Math.max(0, Math.min(100, volume)) : 0;
        audio.state = raw.isMuted() || audio.volume === 0 ? 'muted' : 'audible';
      }
      return audio;
    };
    const player: VideoPlayer = {
      getTime: readTime,
      getVideoId: () => {
        if (!ready || !active() || !raw) return null;
        // Documented as the URL of the currently loaded/playing video:
        // https://developers.google.com/youtube/iframe_api_reference#getVideoUrl
        // Identity may be unavailable during loading, restrictions or ads.
        try {
          const url = new URL(raw.getVideoUrl());
          if (!/^https?:$/.test(url.protocol) || !['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(url.hostname)) return null;
          const ids = url.searchParams.getAll('v');
          const id = ids[0];
          return ids.length === 1 && id !== undefined && /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
        } catch {
          return null;
        }
      },
      getState: () => {
        if (ready && !disposed && raw && state !== 'error') state = decodeState(raw.getPlayerState());
        return state;
      },
      play: () => { if (ready && active()) raw?.playVideo(); },
      pause: () => { if (ready && active()) raw?.pauseVideo(); },
      seek: (seconds) => {
        if (!Number.isFinite(seconds)) throw new RangeError('Seek time must be finite.');
        if (ready && active()) raw?.seekTo(Math.max(0, seconds), true);
      },
      getAudio: readAudio,
      getError: () => lastError,
      destroy,
    };
    void loadApi(window).then((api) => {
      if (!active()) return;
      if (!container.isConnected) {
        fail(new VideoPlayerError('invalid-container', 'The player container was removed before YouTube became ready.'));
        return;
      }
      iframe = container.ownerDocument.createElement('iframe');
      iframe.title = 'YouTube video player';
      iframe.width = '100%';
      iframe.height = '100%';
      iframe.style.border = '0';
      iframe.style.minWidth = '200px';
      iframe.style.minHeight = '200px';
      iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      iframe.allowFullscreen = true;
      // Set before navigating: YouTube error 153 depends on the request identity.
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      const url = new URL(`https://www.youtube.com/embed/${videoId}`);
      url.searchParams.set('enablejsapi', '1');
      url.searchParams.set('origin', window.location.origin);
      url.searchParams.set('widget_referrer', window.location.href);
      url.searchParams.set('controls', '1');
      url.searchParams.set('playsinline', '1');
      url.searchParams.set('autoplay', '0');
      iframe.src = url.href;
      container.append(iframe);
      timer = window.setTimeout(() => fail(new VideoPlayerError('ready-timeout', 'YouTube did not become ready. Check embedding permissions, authentication, network access and content blockers.')), READY_TIMEOUT_MS);
      raw = new api.Player(iframe, {
        events: {
          onReady: (event) => {
            if (!active() || settled) return;
            raw = event.target;
            ready = true;
            window.clearTimeout(timer);
            settled = true;
            resolve(player);
            publish(decodeState(raw.getPlayerState()));
          },
          onStateChange: (event) => {
            if (!active() || (raw && event.target !== raw)) return;
            lastError = null;
            publish(decodeState(event.data));
          },
          onError: (event) => {
            if (!active() || (raw && event.target !== raw)) return;
            fail(youtubeError(event.data));
          },
          onAutoplayBlocked: (event) => {
            if (!active() || (raw && event.target !== raw)) return;
            lastError = new VideoPlayerError('autoplay-blocked', 'The browser blocked playback. Press Play in the visible YouTube player.');
            // This is not a broken media source: retain the real playback state.
            notify(options.onError, lastError);
          },
        },
      });
    }).catch((error: unknown) => {
      fail(error instanceof VideoPlayerError ? error : new VideoPlayerError('api-load', `Could not create the YouTube player: ${error instanceof Error ? error.message : String(error)}`));
    });
  });
}
