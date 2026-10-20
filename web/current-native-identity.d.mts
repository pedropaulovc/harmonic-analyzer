export interface CurrentNativeIdentityProjection {
  readonly kind: 'current-native-identity-projection'
  /** SHA256 of JSON.stringify(parsed frozen table), not a geometry/model hash. */
  readonly mapSha256: string
  /** Exact historical v39 identity-map digest; never replaced by the current map. */
  readonly sourceMapSha256: string
  /** Logical archive role-local ordinals, never rebuilt-native Component2.Name2. */
  readonly occurrenceNamespace: 'archive-role-local'
}
export const CURRENT_NATIVE_IDENTITY_MAP_SHA256: string
export const CURRENT_NATIVE_OCCURRENCE_NAMESPACE: 'archive-role-local'
export function requireCurrentNativeOccurrenceNamespace(namespace: unknown): void
export const CURRENT_NATIVE_IDENTITY_PROJECTION: Readonly<CurrentNativeIdentityProjection>
/** Verifies the actual current naming table before a current native model is consumed. */
export function validateCurrentNativeIdentityTable(table?: unknown): Promise<void>
export function projectCurrentNativePath(path: string, occurrenceNamespace?: string): string
export function projectCurrentNativeNumber(number: string, stem: string, parent?: string | null): string | null
/** Preserves the input's measurement structure and literal numeric types. */
export function projectCurrentNativeMetadata<T>(value: T): T
export function projectCurrentNativeDocument<T extends { nodes?: unknown[] }>(document: T, occurrenceNamespace?: string): T
