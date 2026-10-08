export interface ModelRepresentation {
  schemaVersion: 2
  kind: 'lossless-web-model-representation'
  source: { sha256: string; sourceCommit: string }
  identity: { mapSha256: string; canonicalSha256: string; renamedNodes: number; nodeCount: number }
  representation: { path: 'models/ha-harmonic-analyzer.glb'; sha256: string; byteLength: number; codec: 'EXT_meshopt_compression' }
  pipeline: { version: 2; steps: ['native-identity-map', 'exact-dedup', 'meshopt']; codecVersion: string }
  equivalence: { method: 'decoded-per-drawable-exact-after-native-identity-v2'; semanticSha256: string; drawableCount: number }
}
export const REPRESENTATION_KIND: ModelRepresentation['kind']
export const REPRESENTATION_PATH: ModelRepresentation['representation']['path']
export const PIPELINE_VERSION: 2
export const PIPELINE_STEPS: readonly ['native-identity-map', 'exact-dedup', 'meshopt']
export const NATIVE_IDENTITY_MAP_SHA256: string
export function validateModelRepresentation(value: unknown): ModelRepresentation
export function assertNativeSourceAssociation(value: unknown, native: { modelSha256: string; sourceCommit: string; nativeIdentityMapSha256: string; canonicalModelSha256: string }): ModelRepresentation
export function assertModelRepresentationBytes(value: unknown, native: { modelSha256: string; sourceCommit: string; nativeIdentityMapSha256: string; canonicalModelSha256: string }, actual: { sha256: string; byteLength: number }): ModelRepresentation
