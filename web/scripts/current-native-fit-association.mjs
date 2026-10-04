/** Camera-independent prerequisite shared by explicit current-native fit feature
 * constructors. Replays existing association identity against actual raw typed
 * attribute/index/material bytes and independently original-CPU rest ancestry.
 * No historical world point, camera, source pixel or nearest feature is read.
 * Original decimal local coordinates are identity metadata, not a surface proof.
 * This low-level descriptor check does not admit raw/model bytes; the outer
 * exporter and explicit constructors retain the actual protected-byte gate.
 */
import { CURRENT_NATIVE_RAW_SHA256, canonicalJson, jsonDigest } from './native-model-byte-proof.mjs'
import { describeRawNativePrimitive } from './native-source-feature-bindings.mjs'

const same = (a, b) => canonicalJson(a) === canonicalJson(b)
const finite = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite)
const fail = message => { throw new Error(`Current native fit association: ${message}`) }

/** Returns original raw primitive references, never a copied/altered geometry or
 * old world coordinate. Caller supplies anchored original/current source facts
 * and a single inventoryByPath map from the pinned original CPU closure. */
export function reproveCurrentNativeFitAssociationPrimitives({ nativeModel, inventoryByPath, originalAnchor, anchor, primitiveIndex }) {
  if (!(nativeModel?.primitives instanceof Map) || !(inventoryByPath instanceof Map)) fail('decoded raw primitives and independently original CPU inventory required')
  if (primitiveIndex !== undefined && (!Number.isSafeInteger(primitiveIndex) || primitiveIndex < 0)) fail('explicit raw primitive ordinal must be a nonnegative integer')
  const proof = anchor?.nativeAssociation?.proof
  if (anchor?.nativeAssociation?.status !== 'mapped' || proof?.method !== 'exact-original-native-local-feature-v1'
      || proof.currentSource?.sha256 !== CURRENT_NATIVE_RAW_SHA256 || proof.qualifiedPartPath !== anchor.partPath
      || !originalAnchor || anchor.id !== originalAnchor.id || proof.historicalAnchorSha256 !== jsonDigest(originalAnchor)
      || !finite(anchor.partLocalMetres) || !Array.isArray(proof.primitives)) fail('exact current raw association/original source anchor digest is missing or foreign')
  if (!same(anchor.partLocalMetres, proof.partLocalMetres ?? originalAnchor.partLocalMetres)) fail('exact associated source local point changed without its independently retained coordinate proof')
  const candidates = []
  for (const primitive of nativeModel.primitives.values()) {
    if (primitive.nodeIndex !== proof.currentNodeIndex || primitive.rawPath !== anchor.partPath
        || (primitiveIndex !== undefined && primitive.primitiveIndex !== primitiveIndex)) continue
    const original = inventoryByPath.get(primitive.path)
    if (!original || !same(proof.currentWorldMatrix, Array.from(original.restMatrixF64))) continue
    const rawPrimitive = nativeModel.document.meshes[primitive.meshIndex].primitives[primitive.primitiveIndex]
    const indices = nativeModel.accessor(rawPrimitive.indices)
    const descriptor = describeRawNativePrimitive(primitive, indices)
    if (proof.primitives.some(candidate => same(candidate, descriptor))) candidates.push(primitive)
  }
  return candidates
}
