# Exporter CLI

This package generates printable performance reports by combining JSON data with an HTML template and rendering it with Playwright.

## Prerequisites

- Node.js 18+
- npm 9+
- Playwright system dependencies (run `npx playwright install-deps` on Debian/Ubuntu images)

Install dependencies (Playwright will download a headless Chromium build during install):

```bash
npm ci
```

If you prefer running a build step, the `build` script simply echoes that no compilation is required:

```bash
npm run build
```

## Usage

The CLI loads advertising metrics from a JSON document, injects the content into `templates/report.html`, then uses Chromium to export an A4 PDF and a first-page PNG preview.

```bash
node bin/export-report \
  --data examples/data.sample.json \
  --out out/report.pdf \
  --png out/report.png
```

### Expected output

- `out/report.pdf` – multi-page friendly PDF sized to A4 with background styling
- `out/report.png` – full-page screenshot of the generated report

Both files are created inside `integrations/exporter/out/` unless you override their paths.

## Canva integration stub

The exporter ships with a Canva integration placeholder. Populate `.env` based on `.env.example` to silence configuration warnings:

```bash
cp .env.example .env
# edit .env to add CANVA_API_KEY
```

Calling the CLI will surface whether the Canva credentials are available. The stub currently logs the payload and returns without making external network calls.

## Development notes

- Templates live in `templates/`; update `renderReport.js` if you add new placeholders.
- Example data is stored under `examples/` to keep mock payloads versioned.
- Output paths are created on demand, so you can point to other directories if needed.
