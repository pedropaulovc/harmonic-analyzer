export interface ModelRepresentation {
  schemaVersion: 1
  kind: 'lossless-web-model-representation'
  source: { sha256: string; sourceCommit: string }
  representation: { path: 'models/harmonic-analyzer.glb'; sha256: string; byteLength: number; codec: 'EXT_meshopt_compression' }
  pipeline: { version: 1; steps: ['exact-dedup', 'meshopt']; codecVersion: string }
  equivalence: { method: 'decoded-per-drawable-exact-v1'; semanticSha256: string; drawableCount: number }
}
export const REPRESENTATION_KIND: ModelRepresentation['kind']
export const REPRESENTATION_PATH: ModelRepresentation['representation']['path']
export const PIPELINE_VERSION: 1
export const PIPELINE_STEPS: readonly ['exact-dedup', 'meshopt']
export function validateModelRepresentation(value: unknown): ModelRepresentation
export function assertNativeSourceAssociation(value: unknown, native: { modelSha256: string; sourceCommit: string }): ModelRepresentation
export function assertModelRepresentationBytes(value: unknown, native: { modelSha256: string; sourceCommit: string }, actual: { sha256: string; byteLength: number }): ModelRepresentation
