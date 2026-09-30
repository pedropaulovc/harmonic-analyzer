export interface Video {
  readonly id: string;
  readonly slug: string;
  readonly title: string;
  readonly durationSeconds: number;
  readonly sourceSha256: string;
}

// ffprobe format durations and SHA-256 from the local footage-metadata.json.
// These identify reference footage; playback remains on YouTube, not our host.
export const VIDEOS: readonly Video[] = Object.freeze([
  Object.freeze({ id: 'NAsM30MAHLg', slug: 'intro-history', title: '(1/4) Intro/History: Introducing a 100-year-old mechanical computer', durationSeconds: 218.381, sourceSha256: '595b0ec7b1e1a0b3523d72d33f6e0950bd97dda5ab7032bf91c3e5b9fb7d225d' }),
  Object.freeze({ id: '8KmVDxkia_w', slug: 'synthesis', title: '(2/4) Synthesis: A machine that uses gears, springs and levers to add sines and cosines', durationSeconds: 341.861, sourceSha256: 'a7ac177e0c6eecdfe9b5817716eeb570c43b4590888f007c2cb6de8229ce1725' }),
  Object.freeze({ id: '6dW6VYXp9HM', slug: 'analysis', title: '(3/4) Analysis: Explaining Fourier analysis with a machine', durationSeconds: 244.541, sourceSha256: '5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52' }),
  Object.freeze({ id: 'jfH-NbsmvD4', slug: 'operation', title: '(4/4) Operation: The details of setting up the Harmonic Analyzer', durationSeconds: 707.061, sourceSha256: 'ec0dcdef13700bab2f318f74f9be5591c89b409ae5c5028be468b727284410e3' }),
  Object.freeze({ id: 'rMHw9GCAtE8', slug: 'page-by-page-guide', title: 'Page-by-Page Guide to the Free PDF', durationSeconds: 1184.841, sourceSha256: 'a9e7e1b17aabf62af0afeb165fc04cbb3ac347d43df97f10f8b1d99e89b4df92' }),
  Object.freeze({ id: 'XPQwKRt4Y2k', slug: 'machine-spin', title: 'Bonus: Watch the machine spin around over and over...', durationSeconds: 173.741, sourceSha256: '52caae2e9d617934ae9eb80d6a3d2b1679b31eb9c71e9da741152e84e2d68505' }),
  Object.freeze({ id: '4mBuyixt22U', slug: 'rocker-arms', title: 'Bonus: Rocker arms: sinusoids in two different directions', durationSeconds: 1048.361, sourceSha256: '351bdf54ae64475645ee4904df43af979629c7dab62c47765276faea05adbf4a' }),
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
