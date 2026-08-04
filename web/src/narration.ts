/**
 * The guided tour.
 *
 * The pacing follows the engineerguy series (four videos, transcripts in
 * `references/engineerguy-youtube/*.vtt`) so a viewer who watched those lands
 * in familiar territory. Each chapter names the crank range it plays over, the
 * amplitude-bar setting it uses, and where the camera should be looking.
 *
 * Timings and copy are placeholders until the script is written against the
 * actual transcripts — see `content/script.md`.
 */

import { squareWave, sampleToAmplitudes, CHANNELS } from './kinematics'

export interface Chapter {
  id: string
  title: string
  /** One or two sentences, spoken register. */
  body: string
  /** Crank revolutions this chapter plays across. */
  turns: [number, number]
  /** Amplitude-bar setting for this chapter. */
  amplitudes: number[]
  /** Camera hint: azimuth/elevation in degrees, and what to look at. */
  camera: { az: number; el: number; focus: string }
  /** Which engineerguy video this beat comes from. */
  source: 'intro' | 'synthesis' | 'analysis' | 'operation'
}

const zeros = () => new Array<number>(CHANNELS).fill(0)
const only = (k: number, a = 10) => {
  const v = zeros()
  v[k - 1] = a
  return v
}

export const CHAPTERS: Chapter[] = [
  {
    id: 'introduction',
    title: 'A hundred-year-old computer',
    body: 'This machine adds twenty sine waves together using nothing but gears, cams, springs and levers. Turn the crank and it computes.',
    turns: [0, 4],
    amplitudes: only(1),
    camera: { az: 30, el: 15, focus: 'whole machine' },
    source: 'intro',
  },
  {
    id: 'crank',
    title: 'One input',
    body: 'Everything is driven from a single crank. The force needed varies noticeably through a rotation as twenty springs load and unload.',
    turns: [0, 2],
    amplitudes: only(1),
    camera: { az: 60, el: 10, focus: 'crank' },
    source: 'intro',
  },
  {
    id: 'cone-gears',
    title: 'Twenty speeds from one shaft',
    body: 'The cone gear set is twenty spur gears on one shaft, from six teeth to a hundred and twenty. They all turn together — but each drives its partner at a different rate.',
    turns: [0, 8],
    amplitudes: zeros(),
    camera: { az: 0, el: 25, focus: 'cone gear set' },
    source: 'synthesis',
  },
  {
    id: 'cylinder-gears',
    title: 'Rotation into oscillation',
    body: 'Each cylinder gear carries an eccentric cam. The cam drives a connecting rod up and down, and the rod rocks an arm. Rotation becomes a near-sinusoid.',
    turns: [0, 8],
    amplitudes: only(3),
    camera: { az: -30, el: 5, focus: 'cylinder gear set' },
    source: 'synthesis',
  },
  {
    id: 'amplitude-bars',
    title: 'Setting the coefficients',
    body: 'Sliding a bar along its rocker arm sets how much of that sine wave reaches the sum. At the pivot it contributes nothing; at the far end it contributes with the opposite sign.',
    turns: [0, 4],
    amplitudes: only(1),
    camera: { az: 90, el: 0, focus: 'amplitude bars' },
    source: 'synthesis',
  },
  {
    id: 'summing',
    title: 'Twenty springs, one lever',
    body: 'Twenty small springs pull on one end of the summing lever and one big spring balances the other. It moves only a few millimetres — that tiny motion is the answer.',
    turns: [0, 6],
    amplitudes: squareWave(),
    camera: { az: 20, el: 40, focus: 'summing lever' },
    source: 'synthesis',
  },
  {
    id: 'magnifier',
    title: 'Making it visible',
    body: 'A lever magnifies by up to four, then a wheel — a hundred millimetres over twenty — magnifies by five again. Twenty times, and now you can see it.',
    turns: [0, 6],
    amplitudes: squareWave(),
    camera: { az: 45, el: 30, focus: 'magnifier' },
    source: 'synthesis',
  },
  {
    id: 'synthesis',
    title: 'Drawing a square wave',
    body: 'Set the odd harmonics falling as one over n, turn the crank, and a pen draws a square wave out of twenty cosines.',
    turns: [0, 80],
    amplitudes: squareWave(),
    camera: { az: 75, el: 10, focus: 'pen and platen' },
    source: 'synthesis',
  },
  {
    id: 'analysis',
    title: 'Running it backwards',
    body: 'Sample any function at twenty points, set those samples on the bars, and read the output every two turns of the crank. That reads out the coefficients — this is Fourier analysis, done with gears.',
    turns: [0, 80],
    amplitudes: sampleToAmplitudes((x) => Math.cos(x)),
    camera: { az: 75, el: 10, focus: 'pen and platen' },
    source: 'analysis',
  },
  {
    id: 'setup',
    title: 'Sines or cosines',
    body: 'Swing the cone set out of mesh, line up the notches on the cylinder gears, and a pinion turns them all as one. Notches up is cosines; ninety degrees round is sines.',
    turns: [0, 2],
    amplitudes: zeros(),
    camera: { az: -60, el: 20, focus: 'alignment pinion' },
    source: 'operation',
  },
]

export function chapter(id: string): Chapter | undefined {
  return CHAPTERS.find((c) => c.id === id)
}
