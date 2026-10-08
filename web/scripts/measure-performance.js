// Run with native Windows Chrome: playwright-cli run-code --filename=web/scripts/measure-performance.js
// Navigation and cache conditions are controlled; third-party video bytes are excluded.
async page => {
  await page.addInitScript(() => {
    if (window.__harmonicPerformanceProbe) return;
    const state = window.__harmonicPerformanceProbe = { calls: 0, triangles: 0, frames: 0, paintedFrames: 0, frameCalls: [], frameIntervalsMs: [] };
    const prototype = WebGL2RenderingContext.prototype;
    for (const name of ['drawElements', 'drawArrays', 'drawElementsInstanced', 'drawArraysInstanced']) {
      const original = prototype[name];
      prototype[name] = function (...args) {
        // Restrict counts to the application's canvas, not the source iframe.
        if (this.canvas.id === 'stage') {
          state.calls++;
          const count = args[name.startsWith('drawElements') ? 1 : 2];
          const instances = name.endsWith('Instanced') ? args[name.startsWith('drawElements') ? 4 : 3] : 1;
          if (args[0] === this.TRIANGLES) state.triangles += count * instances / 3;
        }
        return original.apply(this, args);
      };
    }
    let previousCalls = 0;
    let previousTime = 0;
    const frame = time => {
      const calls = state.calls - previousCalls;
      state.frames++;
      if (calls) {
        state.paintedFrames++;
        state.frameCalls.push(calls);
        if (previousTime) state.frameIntervalsMs.push(time - previousTime);
        previousTime = time;
      }
      previousCalls = state.calls;
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Performance.enable');
  const samples = [];
  const collect = async label => {
    const start = await cdp.send('Performance.getMetrics');
    const before = await page.evaluate(() => {
      const probe = window.__harmonicPerformanceProbe;
      probe.frameCalls.length = 0;
      probe.frameIntervalsMs.length = 0;
      return { calls: probe.calls, triangles: probe.triangles, frames: probe.frames, paintedFrames: probe.paintedFrames };
    });
    await page.waitForTimeout(5000);
    const end = await cdp.send('Performance.getMetrics');
    const after = await page.evaluate(() => ({ ...window.__harmonicPerformanceProbe }));
    const percentile = (values, fraction) => {
      const ordered = values.toSorted((a, b) => a - b);
      return ordered[Math.floor((ordered.length - 1) * fraction)] ?? null;
    };
    return {
      label, wallSeconds: end.metrics.find(row => row.name === 'Timestamp').value - start.metrics.find(row => row.name === 'Timestamp').value,
      calls: after.calls - before.calls, triangles: after.triangles - before.triangles,
      frames: after.frames - before.frames, paintedFrames: after.paintedFrames - before.paintedFrames,
      callsPerPaintedFrame: percentile(after.frameCalls, 0.5), frameIntervalMedianMs: percentile(after.frameIntervalsMs, 0.5), frameIntervalP95Ms: percentile(after.frameIntervalsMs, 0.95),
      instrumentedCpuSeconds: Object.fromEntries(['TaskDuration', 'ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration'].map(name => [name, end.metrics.find(row => row.name === name).value - start.metrics.find(row => row.name === name).value])),
      heapBytes: end.metrics.find(row => row.name === 'JSHeapUsedSize').value,
    };
  };
  try {
    for (let run = 0; run < 3; run++) {
      await cdp.send('Network.clearBrowserCache');
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('#loading').waitFor({ state: 'hidden', timeout: 60000 });
      await page.waitForTimeout(2000);
      const resources = await page.evaluate(() => performance.getEntriesByType('resource').filter(row => /\/assets\/|\.glb(?:\?|$)/.test(row.name)).map(row => ({ url: row.name, transferBytes: row.transferSize, decodedBytes: row.decodedBodySize, durationMs: row.duration })));
      const idle = await collect('idle');
      await page.locator('summary').filter({ hasText: 'Mechanism controls' }).click();
      await page.locator('#manual-run').click();
      await page.waitForTimeout(1000);
      const motion = await collect('manual-crank');
      await page.locator('#manual-run').click();
      samples.push({ run: run + 1, resources, idle, motion });
    }
    return {
      url: page.url(), browser: await page.evaluate(() => navigator.userAgent), viewport: await page.evaluate(() => ({ width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio })),
      conditions: 'native browser; cold HTTP cache each navigation; no network/CPU throttling; five-second idle and active windows; three runs; ordinary WebGL2 draw instrumentation adds CPU overhead; use measure-cpu.js in a fresh session for CPU comparison',
      gpu: await page.evaluate(() => {
        const gl = document.querySelector('#stage').getContext('webgl2');
        const extension = gl.getExtension('WEBGL_debug_renderer_info');
        return extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : 'unavailable';
      }),
      samples,
    };
  } finally {
    await cdp.detach();
  }
}
