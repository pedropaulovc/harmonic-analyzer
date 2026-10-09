// Run in a fresh native Chrome session: no draw-call instrumentation is installed.
async page => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Performance.enable');
  const collect = async label => {
    await page.bringToFront();
    const environment = () => page.evaluate(() => ({ visibility: document.visibilityState, focus: document.hasFocus() ? 'focused' : 'blurred', manualState: document.querySelector('#manual-run').textContent }));
    const environmentBefore = await environment();
    const stateBefore = await page.locator('#playback-status').textContent();
    const start = await cdp.send('Performance.getMetrics');
    await page.waitForTimeout(5000);
    const end = await cdp.send('Performance.getMetrics');
    const stateAfter = await page.locator('#playback-status').textContent();
    const environmentAfter = await environment();
    const foreground = environmentBefore.visibility === 'visible' && environmentAfter.visibility === 'visible' && environmentBefore.focus === 'focused' && environmentAfter.focus === 'focused';
    const manualRunning = label !== 'manual-crank' || (environmentBefore.manualState === 'Stop crank' && environmentAfter.manualState === 'Stop crank');
    const followingPattern = /^Playing · Approximate source-following/;
    return {
      label, stateBefore, stateAfter, environmentBefore, environmentAfter,
      endpointStatus: !foreground || !manualRunning ? 'interrupted' : label !== 'source-following' || (followingPattern.test(stateBefore ?? '') && followingPattern.test(stateAfter ?? '')) ? 'valid' : 'changed-state',
      cpuSeconds: Object.fromEntries(['TaskDuration', 'ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration'].map(name => [name, end.metrics.find(row => row.name === name).value - start.metrics.find(row => row.name === name).value])),
      wallSeconds: end.metrics.find(row => row.name === 'Timestamp').value - start.metrics.find(row => row.name === 'Timestamp').value,
      heapBytes: end.metrics.find(row => row.name === 'JSHeapUsedSize').value,
    };
  };
  const samples = [];
  try {
    for (let run = 0; run < 3; run++) {
      await cdp.send('Network.clearBrowserCache');
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('#loading').waitFor({ state: 'hidden', timeout: 60000 });
      await page.waitForTimeout(2000);
      const idle = await collect('idle');
      await page.locator('summary').filter({ hasText: 'Mechanism controls' }).click();
      await page.locator('#manual-run').click();
      await page.waitForTimeout(1000);
      const manual = await collect('manual-crank');
      await page.locator('#manual-run').click();
      await page.locator('#pause-video').click();
      await page.getByText(/Playing · Approximate source-following/, { exact: false }).waitFor({ timeout: 30000 });
      const following = await collect('source-following');
      await page.locator('#pause-video').click();
      samples.push({ run: run + 1, idle, manual, following });
    }
    return {
      url: page.url(), browser: await page.evaluate(() => navigator.userAgent), viewport: await page.evaluate(() => ({ width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio })),
      conditions: 'fresh native browser session; no WebGL wrappers; cold HTTP cache each navigation; no network/CPU throttling; one five-second window per mode per run; three runs; source-following validity checks window endpoints, not continuous playback',
      samples,
    };
  } finally {
    await cdp.detach();
  }
}
