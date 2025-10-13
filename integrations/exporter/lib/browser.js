const fs = require('fs/promises');
const path = require('path');
const { chromium } = require('playwright-core');
const chromiumBinary = require('@sparticuz/chromium');

async function ensureDir(filePath) {
  const dir = path.dirname(filePath);
  await fs.mkdir(dir, { recursive: true });
}

async function renderToFiles(html, { pdfPath, pngPath }) {
  if (!pdfPath && !pngPath) {
    throw new Error('At least one output option (--out or --png) must be provided.');
  }

  let browser;
  try {
    const launchOptions = {
      args: chromiumBinary.args,
      executablePath: await chromiumBinary.executablePath(),
    };

    if (chromiumBinary.headless !== undefined) {
      launchOptions.headless = chromiumBinary.headless;
    }

    browser = await chromium.launch(launchOptions);

    const page = await browser.newPage();
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.setContent(html, { waitUntil: 'networkidle' });

    if (pdfPath) {
      await ensureDir(pdfPath);
      await page.pdf({
        path: pdfPath,
        format: 'A4',
        printBackground: true,
        margin: { top: '20mm', right: '16mm', bottom: '20mm', left: '16mm' },
      });
    }

    if (pngPath) {
      await ensureDir(pngPath);
      await page.screenshot({ path: pngPath, fullPage: true });
    }
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

module.exports = {
  renderToFiles,
};
