import * as THREE from 'three'

/** Raw GPU-helper output, not a qualification decision or an onscreen receipt. */
export interface NativeQualificationRasterResult {
  /** Independent snapshots: subsequent captures never write into these arrays. */
  readonly colorRgba8: Uint8Array
  readonly depthPackedRgba8: Uint8Array
  readonly width: number
  readonly height: number
  readonly origin: 'bottom-left'
  readonly targetSemantics: 'actual-production-material-offscreen'
  readonly sampleCount: 0
  readonly textureColorSpace: string
  readonly depthPackedTextureColorSpace: string
  readonly depthPacking: 'three-rgba-depth-v1'
  readonly threeRevision: string
  readonly depthBits: number
  readonly depthAttachment: Readonly<{
    /** GL FRAMEBUFFER_ATTACHMENT_COMPONENT_TYPE, queried from the bound FBO. */
    componentType: number
    /** Installed Three constants from the attached DepthTexture. */
    textureFormat: number
    textureType: number
  }>
}

const PACK_VERTEX = `
varying vec2 depthUv;
void main() {
  depthUv = position.xy * 0.5 + 0.5;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`

const PACK_FRAGMENT = `
uniform sampler2D sourceDepth;
varying vec2 depthUv;
#include <packing>
void main() {
  gl_FragColor = packDepthToRGBA(texture2D(sourceDepth, depthUv).r);
}
`

/**
 * Opt-in resources for the supplied renderer. The caller owns scene/camera
 * preparation, material swaps and marker visibility; this helper inspects none
 * of that graph. Normal playback need not construct or call this helper.
 *
 * Both targets are single-sample RGBA8. Production color uses Three's regular
 * linear-sRGB offscreen pipeline, not canvas/MSAA/output-tone-mapping semantics.
 * Depth is sampled from that same production render's actual depth attachment,
 * then packed using the installed ShaderChunk packing implementation. Decode
 * with that implementation's unpackRGBAToDepth, not older Three byte ordering.
 */
export class NativeQualificationRasterCapture {
  private readonly gl: WebGL2RenderingContext
  private readonly productionTarget: THREE.WebGLRenderTarget
  private readonly packingTarget: THREE.WebGLRenderTarget
  private readonly depthTexture: THREE.DepthTexture
  private readonly packingGeometry: THREE.BufferGeometry
  private readonly packingMaterial: THREE.ShaderMaterial
  private readonly packingScene = new THREE.Scene()
  private readonly packingCamera = new THREE.Camera()
  private readonly savedViewport = new THREE.Vector4()
  private readonly savedScissor = new THREE.Vector4()
  private readonly savedCurrentViewport = new THREE.Vector4()
  private readonly savedCurrentScissor = new THREE.Vector4()
  private readonly savedTargetViewport = new THREE.Vector4()
  private readonly savedTargetScissor = new THREE.Vector4()
  private readonly savedClearColor = new THREE.Color()
  private colorReadback: Uint8Array | null = null
  private depthReadback: Uint8Array | null = null
  private disposed = false
  private capturing = false

  constructor(private readonly renderer: THREE.WebGLRenderer) {
    const context = renderer.getContext()
    if (typeof (context as WebGL2RenderingContext).texStorage2D !== 'function') {
      throw new Error('Native raster capture requires an existing WebGL2 renderer.')
    }
    this.gl = context as WebGL2RenderingContext
    this.assertContext()

    this.depthTexture = new THREE.DepthTexture(1, 1, THREE.UnsignedIntType)
    this.depthTexture.format = THREE.DepthFormat
    this.depthTexture.minFilter = THREE.NearestFilter
    this.depthTexture.magFilter = THREE.NearestFilter
    this.depthTexture.generateMipmaps = false
    this.depthTexture.compareFunction = null

    this.productionTarget = new THREE.WebGLRenderTarget(1, 1, {
      format: THREE.RGBAFormat,
      type: THREE.UnsignedByteType,
      internalFormat: 'RGBA8',
      colorSpace: THREE.LinearSRGBColorSpace,
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      generateMipmaps: false,
      depthBuffer: true,
      stencilBuffer: false,
      depthTexture: this.depthTexture,
      samples: 0,
    })
    this.packingTarget = new THREE.WebGLRenderTarget(1, 1, {
      format: THREE.RGBAFormat,
      type: THREE.UnsignedByteType,
      internalFormat: 'RGBA8',
      colorSpace: THREE.NoColorSpace,
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      generateMipmaps: false,
      depthBuffer: false,
      stencilBuffer: false,
      samples: 0,
    })
    this.packingGeometry = new THREE.BufferGeometry()
    this.packingGeometry.setAttribute('position', new THREE.Float32BufferAttribute([
      -1, -1, 0,
      3, -1, 0,
      -1, 3, 0,
    ], 3))
    this.packingMaterial = new THREE.ShaderMaterial({
      name: 'NativeQualificationDepthTexturePacking',
      uniforms: { sourceDepth: { value: this.depthTexture } },
      vertexShader: PACK_VERTEX,
      fragmentShader: PACK_FRAGMENT,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
      blending: THREE.NoBlending,
      dithering: false,
    })
    const triangle = new THREE.Mesh(this.packingGeometry, this.packingMaterial)
    triangle.frustumCulled = false
    triangle.matrixAutoUpdate = false
    this.packingScene.add(triangle)
  }

  /** Explicitly resize the same targets and CPU staging buffers; no rendering. */
  resize(width: number, height: number): void {
    this.assertUsable()
    this.assertGlSuccess('preparing capture resources')
    if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width <= 0 || height <= 0) {
      throw new Error('Native raster capture dimensions must be positive safe integers.')
    }
    const byteLength = width * height * 4
    if (!Number.isSafeInteger(byteLength)) {
      throw new Error(`Native raster capture ${width}x${height} exceeds CPU readback capacity.`)
    }
    if (this.productionTarget.width === width && this.productionTarget.height === height && this.colorReadback !== null) return

    const gl = this.gl
    const maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number
    const maxRenderbufferSize = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE) as number
    const maxViewport = gl.getParameter(gl.MAX_VIEWPORT_DIMS) as Int32Array | null
    const maxViewportWidth = maxViewport?.[0]
    const maxViewportHeight = maxViewport?.[1]
    this.assertGlSuccess('querying capture capacity')
    if (!Number.isInteger(maxTextureSize) || maxTextureSize <= 0 ||
        !Number.isInteger(maxRenderbufferSize) || maxRenderbufferSize <= 0 ||
        maxViewportWidth === undefined || maxViewportHeight === undefined ||
        maxViewportWidth <= 0 || maxViewportHeight <= 0) {
      throw new Error('Native raster capture cannot query WebGL2 target capacity.')
    }
    if (width > maxTextureSize || height > maxTextureSize ||
        width > maxRenderbufferSize || height > maxRenderbufferSize ||
        width > maxViewportWidth || height > maxViewportHeight) {
      throw new Error(`Native raster capture ${width}x${height} exceeds WebGL2 target/viewport capacity.`)
    }

    let colorReadback: Uint8Array
    let depthReadback: Uint8Array
    try {
      colorReadback = new Uint8Array(byteLength)
      depthReadback = new Uint8Array(byteLength)
    } catch (cause) {
      throw new Error(`Native raster capture cannot allocate ${byteLength}-byte readback buffers.`, { cause })
    }
    this.productionTarget.setSize(width, height)
    this.packingTarget.setSize(width, height)
    this.colorReadback = colorReadback
    this.depthReadback = depthReadback
  }

  /** Synchronous opt-in render/readback; changing dimensions calls resize(). */
  capture(scene: THREE.Scene, camera: THREE.Camera, width: number, height: number): NativeQualificationRasterResult {
    this.resize(width, height)
    const colorReadback = this.colorReadback!
    const depthReadback = this.depthReadback!
    const renderer = this.renderer
    const gl = this.gl
    const target = renderer.getRenderTarget()
    const activeCubeFace = renderer.getActiveCubeFace()
    const activeMipmapLevel = renderer.getActiveMipmapLevel()
    renderer.getViewport(this.savedViewport)
    renderer.getScissor(this.savedScissor)
    renderer.getCurrentViewport(this.savedCurrentViewport)
    this.savedCurrentScissor.fromArray(gl.getParameter(gl.SCISSOR_BOX) as Int32Array)
    const scissorTest = renderer.getScissorTest()
    const currentScissorTest = gl.isEnabled(gl.SCISSOR_TEST)
    const targetScissorTest = target?.scissorTest ?? false
    if (target !== null) {
      this.savedTargetViewport.copy(target.viewport)
      this.savedTargetScissor.copy(target.scissor)
    }
    renderer.getClearColor(this.savedClearColor)
    const clearAlpha = renderer.getClearAlpha()
    const autoClear = renderer.autoClear
    const autoClearColor = renderer.autoClearColor
    const autoClearDepth = renderer.autoClearDepth
    const autoClearStencil = renderer.autoClearStencil
    const xrEnabled = renderer.xr.enabled
    const ditherEnabled = gl.isEnabled(gl.DITHER)
    const packAlignment = gl.getParameter(gl.PACK_ALIGNMENT) as number
    const packRowLength = gl.getParameter(gl.PACK_ROW_LENGTH) as number
    const packSkipPixels = gl.getParameter(gl.PACK_SKIP_PIXELS) as number
    const packSkipRows = gl.getParameter(gl.PACK_SKIP_ROWS) as number
    const pixelPackBuffer = gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) as WebGLBuffer | null
    this.assertGlSuccess('saving renderer state')

    this.capturing = true
    try {
      renderer.xr.enabled = false
      renderer.autoClear = true
      renderer.autoClearColor = true
      renderer.autoClearDepth = true
      renderer.autoClearStencil = false
      gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null)
      gl.pixelStorei(gl.PACK_ALIGNMENT, 1)
      gl.pixelStorei(gl.PACK_ROW_LENGTH, 0)
      gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0)
      gl.pixelStorei(gl.PACK_SKIP_ROWS, 0)

      // Target viewports are backing pixels. renderer.setViewport would instead
      // multiply by the canvas pixel ratio, so it must not set capture dimensions.
      renderer.setRenderTarget(this.productionTarget)
      this.assertFramebuffer('production color/depth')
      const depthObjectType = gl.getFramebufferAttachmentParameter(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE) as number
      const depthBits = gl.getFramebufferAttachmentParameter(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.FRAMEBUFFER_ATTACHMENT_DEPTH_SIZE) as number
      const depthComponentType = gl.getFramebufferAttachmentParameter(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.FRAMEBUFFER_ATTACHMENT_COMPONENT_TYPE) as number
      const samples = gl.getParameter(gl.SAMPLES) as number
      this.assertGlSuccess('querying the actual depth attachment')
      if (depthObjectType !== gl.TEXTURE || !Number.isInteger(depthBits) || depthBits <= 0 ||
          depthComponentType !== gl.UNSIGNED_NORMALIZED || samples !== 0) {
        throw new Error('Native raster capture requires queryable, single-sample unsigned-normalized texture depth metadata.')
      }
      // Seed the configured renderer clear, not a preceding scene's GPU clear.
      // renderer.render then retains this scene's real color/texture background.
      renderer.setClearColor(this.savedClearColor, clearAlpha)
      renderer.render(scene, camera)
      this.assertGlSuccess('rendering production materials')
      renderer.readRenderTargetPixels(this.productionTarget, 0, 0, width, height, colorReadback)
      this.assertGlSuccess('reading production RGBA8')

      renderer.setRenderTarget(this.packingTarget)
      this.assertFramebuffer('depth packing')
      // ShaderMaterial.dithering controls a shader chunk, not fixed GL DITHER.
      // Packing must not perturb byte channels after packDepthToRGBA.
      renderer.state.disable(gl.DITHER)
      renderer.setClearColor(this.savedClearColor, clearAlpha)
      renderer.render(this.packingScene, this.packingCamera)
      this.assertGlSuccess('packing the production depth texture')
      renderer.readRenderTargetPixels(this.packingTarget, 0, 0, width, height, depthReadback)
      this.assertGlSuccess('reading packed depth RGBA8')

      // Nonempty typed arrays cannot be Object.freeze()d. Freeze the receipt and
      // metadata, and give the caller its own byte storage, never reused here.
      try {
        return Object.freeze({
          colorRgba8: colorReadback.slice(),
          depthPackedRgba8: depthReadback.slice(),
          width,
          height,
          origin: 'bottom-left',
          targetSemantics: 'actual-production-material-offscreen',
          sampleCount: 0,
          textureColorSpace: this.productionTarget.texture.colorSpace,
          depthPackedTextureColorSpace: this.packingTarget.texture.colorSpace,
          depthPacking: 'three-rgba-depth-v1',
          threeRevision: THREE.REVISION,
          depthBits,
          depthAttachment: Object.freeze({
            componentType: depthComponentType,
            textureFormat: this.depthTexture.format,
            textureType: this.depthTexture.type,
          }),
        })
      } catch (cause) {
        throw new Error('Native raster capture cannot allocate independent receipt bytes.', { cause })
      }
    } finally {
      try {
        renderer.autoClear = autoClear
        renderer.autoClearColor = autoClearColor
        renderer.autoClearDepth = autoClearDepth
        renderer.autoClearStencil = autoClearStencil
        renderer.xr.enabled = xrEnabled
        renderer.setViewport(this.savedViewport)
        renderer.setScissor(this.savedScissor)
        renderer.setScissorTest(scissorTest)
        try {
          if (target !== null) {
            // Binding copies target-owned pixel rectangles into Three's current
            // viewport/scissor. Restore the active rectangles without changing
            // the caller's persistent target configuration or logical settings.
            target.viewport.copy(this.savedCurrentViewport)
            target.scissor.copy(this.savedCurrentScissor)
            target.scissorTest = currentScissorTest
            try {
              renderer.setRenderTarget(target, activeCubeFace, activeMipmapLevel)
            } finally {
              target.viewport.copy(this.savedTargetViewport)
              target.scissor.copy(this.savedTargetScissor)
              target.scissorTest = targetScissorTest
            }
          } else {
            renderer.setRenderTarget(null, activeCubeFace, activeMipmapLevel)
            // setRenderTarget floors canvas rectangles; setViewport rounds them.
            // Preserve whichever public operation produced the saved viewport.
            this.savedTargetViewport.copy(this.savedViewport).multiplyScalar(renderer.getPixelRatio()).floor()
            if (!this.savedTargetViewport.equals(this.savedCurrentViewport)) renderer.setViewport(this.savedViewport)
            renderer.state.viewport(this.savedCurrentViewport)
            renderer.state.scissor(this.savedCurrentScissor)
            renderer.state.setScissorTest(currentScissorTest)
          }
        } finally {
          renderer.setClearColor(this.savedClearColor, clearAlpha)
        }
      } finally {
        try {
          if (ditherEnabled) renderer.state.enable(gl.DITHER)
          else renderer.state.disable(gl.DITHER)
          gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pixelPackBuffer)
          gl.pixelStorei(gl.PACK_ALIGNMENT, packAlignment)
          gl.pixelStorei(gl.PACK_ROW_LENGTH, packRowLength)
          gl.pixelStorei(gl.PACK_SKIP_PIXELS, packSkipPixels)
          gl.pixelStorei(gl.PACK_SKIP_ROWS, packSkipRows)
        } finally {
          this.capturing = false
        }
      }
    }
  }

  /** Release only owned resources; never dispose the supplied renderer. */
  dispose(): void {
    if (this.disposed) return
    if (this.capturing) throw new Error('Cannot dispose native raster capture during a capture.')
    this.disposed = true
    // Dispose the depth texture exactly once, including before a first capture.
    this.productionTarget.depthTexture = null
    this.productionTarget.dispose()
    this.depthTexture.dispose()
    this.packingTarget.dispose()
    this.packingGeometry.dispose()
    this.packingMaterial.dispose()
    this.packingMaterial.uniforms.sourceDepth!.value = null
    this.packingScene.clear()
    this.colorReadback = null
    this.depthReadback = null
  }

  private assertUsable(): void {
    if (this.disposed) throw new Error('Native raster capture has been disposed.')
    if (this.capturing) throw new Error('Native raster capture cannot be reentered.')
    this.assertContext()
  }

  private assertContext(): void {
    if (this.gl.isContextLost()) throw new Error('Native raster capture requires an available WebGL2 context.')
  }

  private assertGlSuccess(operation: string): void {
    this.assertContext()
    const error = this.gl.getError()
    if (error !== this.gl.NO_ERROR) {
      throw new Error(`Native raster capture failed while ${operation}: WebGL error 0x${error.toString(16)}.`)
    }
  }

  private assertFramebuffer(label: string): void {
    const status = this.gl.checkFramebufferStatus(this.gl.FRAMEBUFFER)
    if (status !== this.gl.FRAMEBUFFER_COMPLETE) {
      throw new Error(`Native raster capture ${label} framebuffer is unavailable: 0x${status.toString(16)}.`)
    }
  }
}
