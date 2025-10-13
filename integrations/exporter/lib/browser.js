const fs = require('fs/promises');
const path = require('path');
const { chromium } = require('playwright');

async function ensureDir(filePath) {
  const dir = path.dirname(filePath);
  await fs.mkdir(dir, { recursive: true });
}

async function renderToFiles(html, { pdfPath, pngPath }) {
  if (!pdfPath && !pngPath) {
    throw new Error('At least one output option (--out or --png) must be provided.');
  }

  const browser = await chromium.launch();
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

  await browser.close();
}

module.exports = {
  renderToFiles,
};
