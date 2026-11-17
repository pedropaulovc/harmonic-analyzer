export interface Video {
  readonly id: string;
  readonly slug: string;
  readonly title: string;
  readonly durationSeconds: number;
  /** Source frame rate, for the shot editor's frame step. */
  readonly fps: number;
}

// ffprobe format durations and frame rates of the published footage.
export const VIDEOS: readonly Video[] = Object.freeze([
  Object.freeze({ id: 'NAsM30MAHLg', slug: 'intro-history', title: '(1/4) Intro/History: Introducing a 100-year-old mechanical computer', durationSeconds: 218.381, fps: 30000 / 1001 }),
  Object.freeze({ id: '8KmVDxkia_w', slug: 'synthesis', title: '(2/4) Synthesis: A machine that uses gears, springs and levers to add sines and cosines', durationSeconds: 341.861, fps: 24000 / 1001 }),
  Object.freeze({ id: '6dW6VYXp9HM', slug: 'analysis', title: '(3/4) Analysis: Explaining Fourier analysis with a machine', durationSeconds: 244.541, fps: 30000 / 1001 }),
  Object.freeze({ id: 'jfH-NbsmvD4', slug: 'operation', title: '(4/4) Operation: The details of setting up the Harmonic Analyzer', durationSeconds: 707.061, fps: 30000 / 1001 }),
  Object.freeze({ id: 'XPQwKRt4Y2k', slug: 'machine-spin', title: 'Bonus: Watch the machine spin around over and over...', durationSeconds: 173.741, fps: 24000 / 1001 }),
  Object.freeze({ id: '4mBuyixt22U', slug: 'rocker-arms', title: 'Bonus: Rocker arms: sinusoids in two different directions', durationSeconds: 1048.361, fps: 24000 / 1001 }),
]);

export class InvalidVideoSelectionError extends Error {
  readonly code = 'invalid-video-selection';

  constructor(readonly selector: string, message = `Unknown video selection: ${JSON.stringify(selector)}.`) {
    super(message);
    this.name = 'InvalidVideoSelectionError';
  }
}

/** Only an absent selector defaults. Empty or repeated explicit selectors are invalid. */
export function resolveVideo(search: string): Video {
  const selectors = new URLSearchParams(search).getAll('video');
  if (selectors.length === 0) return VIDEOS[0]!;
  const selector = selectors[0]!;
  if (selectors.length !== 1) {
    throw new InvalidVideoSelectionError(selector, 'Specify exactly one video query parameter.');
  }
  const video = VIDEOS.find((entry) => entry.id === selector || entry.slug === selector);
  if (!video) throw new InvalidVideoSelectionError(selector);
  return video;
}
