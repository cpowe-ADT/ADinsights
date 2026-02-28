#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import process from 'node:process';
import { setTimeout as delay } from 'node:timers/promises';

import { chromium } from 'playwright';

const previewPort = process.env.PREVIEW_PORT || '4173';
const routePath = process.env.PREVIEW_ROUTE || '/dashboards/campaigns';
const smokeUrl = `http://127.0.0.1:${previewPort}${routePath}`;
const readinessUrl = `http://127.0.0.1:${previewPort}/`;

const preview = spawn('npm', ['run', 'preview', '--', '--host', '--port', previewPort], {
  detached: process.platform !== 'win32',
  stdio: ['ignore', 'pipe', 'pipe'],
});

preview.stdout.on('data', (chunk) => {
  process.stdout.write(chunk);
});
preview.stderr.on('data', (chunk) => {
  process.stderr.write(chunk);
});

async function shutdown() {
  if (preview.exitCode !== null || preview.signalCode) {
    return;
  }

  try {
    if (process.platform !== 'win32' && typeof preview.pid === 'number') {
      process.kill(-preview.pid, 'SIGTERM');
    } else {
      preview.kill('SIGTERM');
    }
  } catch {
    // Ignore kill errors if the process already exited.
  }

  await Promise.race([once(preview, 'exit'), delay(2_000)]);

  if (preview.exitCode === null && !preview.signalCode) {
    try {
      if (process.platform !== 'win32' && typeof preview.pid === 'number') {
        process.kill(-preview.pid, 'SIGKILL');
      } else {
        preview.kill('SIGKILL');
      }
    } catch {
      // Ignore kill errors if the process already exited.
    }
  }
}

const fail = async (message) => {
  console.error(`preview-route-smoke failed: ${message}`);
  await shutdown();
  await delay(250);
  process.exit(1);
};

async function waitForPreview(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // Preview server not ready yet.
    }
    await delay(500);
  }
  await fail(`preview server did not become ready at ${url}`);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
const hardTimeout = setTimeout(() => {
  void fail(`timed out while checking ${smokeUrl}`);
}, 120_000);
hardTimeout.unref();

try {
  await waitForPreview(readinessUrl);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const pageErrors = [];

  page.on('pageerror', (error) => {
    pageErrors.push(error?.stack || error?.message || String(error));
  });

  const response = await page.goto(smokeUrl, {
    waitUntil: 'networkidle',
    timeout: 30_000,
  });

  if (!response || response.status() >= 400) {
    await browser.close();
    await fail(`route ${smokeUrl} returned status ${response ? response.status() : 'no response'}`);
  }

  const bodyText = await page.evaluate(() => (document.body?.innerText || '').trim());

  if (pageErrors.length > 0) {
    await browser.close();
    await fail(`runtime page errors detected:\n${pageErrors.join('\n')}`);
  }

  if (!bodyText) {
    await browser.close();
    await fail(`route ${smokeUrl} rendered empty body text`);
  }

  console.log(`preview-route-smoke passed for ${smokeUrl}`);
  await browser.close();
  clearTimeout(hardTimeout);
  await shutdown();
  await delay(250);
  process.exit(0);
} catch (error) {
  clearTimeout(hardTimeout);
  await fail(error?.stack || error?.message || String(error));
}
