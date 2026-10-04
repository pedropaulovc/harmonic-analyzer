import type { Binding } from './src/bindings'
import type { CameraRecord } from './src/scene'
import type { NativeNumericOutput, NativeSubmittedPrimitive, NativeSerializedBinding } from './src/native-qualification-types'
export function canonicalJson(value: unknown): string
export function serializeNativeBinding(binding: Binding | null): NativeSerializedBinding | null
export function nativeExpectedCameraSnapshot(camera: CameraRecord, logicalDimensions: readonly [number, number]): CameraRecord
export function nativeProgramSource(vertexShader: string, fragmentShader: string): string
export function nativeGeometryUniforms<T extends { name: string }>(uniforms: readonly T[], vertexShaderText?: string): T[]
export function nativeGeometryStateDescriptor(submitted: NativeSubmittedPrimitive, vertexShaderText?: string): Record<string, unknown>
export function nativeSubmissionStateDescriptor(submitted: NativeSubmittedPrimitive): Record<string, unknown>
export const nativeTFVaryingNames: Readonly<Record<NativeNumericOutput['fields'][number]['name'], string>>
export function instrumentNativeVertexShader(source: string, fields: NativeNumericOutput['fields']): string
