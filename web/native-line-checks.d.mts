export const NATIVE_LINE_STATIONS: readonly number[]
export function nativeLineEndpointId(viewId: string, lineId: string, station: number): string
export function fixedNativeLinePart(partPath: string, authority: { paths: Set<string>; bindings: { motion: string; pattern: RegExp }[] }): boolean
export function nativeLineReadbackResidual(projected: [number, number][], observed: [number, number][]): { perpendicularErrorsPx: number[]; nativeSegmentCoversObservation: boolean }
