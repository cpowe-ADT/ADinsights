# Report export CLI overview

## Purpose

The report exporter turns aggregated advertising metrics into printable deliverables. It merges JSON payloads with the HTML template in `integrations/exporter/templates/`, renders the report in headless Chromium, and emits an A4 PDF plus a first-page PNG preview. This makes it easy to hand off consistent performance summaries without opening the full BI stack.

The application report export flow (`POST /api/reports/{id}/exports/`) now uses this renderer for
generic PDF/PNG requests and writes CSV artifacts directly from the tenant-scoped aggregate
snapshot. A job is marked `completed` only after its requested artifact exists and is non-empty;
download it through `GET /api/exports/{job_id}/download/`.
CSV artifacts neutralize formula-leading text cells before download, and both generic and Google
Ads artifact download handlers reject paths that escape the expected export directory.
In container profiles, the API and summary worker use `REPORT_EXPORT_ARTIFACT_ROOT` on a shared
volume so successfully rendered worker artifacts are immediately downloadable by the API.

## Setup

1. Install prerequisites (Node.js 18+). Linux deployments use the bundled
   native Chromium executable configured with `CHROMIUM_EXECUTABLE_PATH`; this keeps container
   rendering compatible with both x86-64 and ARM64 images. Other Linux runtimes may use the
   bundled `@sparticuz/chromium` build. Local macOS/Windows development uses Playwright's
   installed platform browser; run `npx playwright-core install chromium` if no cached browser
   exists.
2. Install dependencies:
   ```bash
   cd integrations/exporter
   npm ci
   ```
3. Optional: run the no-op build script if you want to verify the package.json scripts wire up correctly:
   ```bash
   npm run build
   ```

## Running the sample export

The CLI ships with a sample payload under `integrations/exporter/examples/data.sample.json`. Generate a report and preview using the bundled data:

```bash
node bin/export-report \
  --data examples/data.sample.json \
  --out out/sample-report.pdf \
  --png out/sample-report.png
```

The command creates an `out/` directory inside `integrations/exporter/` on demand. With the current template, the sample run produces:

- `integrations/exporter/out/sample-report.pdf` (~71 KB)
- `integrations/exporter/out/sample-report.png` (~53 KB)

Your exact sizes may vary slightly when templates or assets change, but both files are regenerated every execution. If you point `--out` or `--png` to another location, those paths will be created for you.

## Expected output and artifacts

The PDF captures all report pages with background graphics enabled, while the PNG is a full-page render of the first sheet—handy for quick previews or embedding into slides. Keep the `out/` directory in `.gitignore`; it is transient output. When the exporter runs, it also invokes the Canva stub and logs whether Canva credentials are present so ops teams can verify integration readiness.

## Environment configuration

Future Canva exports require authenticated calls. Copy `.env.example` (in the exporter package) to `.env` and populate the placeholder values—currently just `CANVA_API_KEY`. The CLI loads this file automatically via `dotenv`, enabling Playwright rendering to continue even when Canva credentials are absent. Until real Canva uploads land, the stub logs the payload and exits, but wiring the API key now avoids runtime warnings.

## Using custom JSON payloads

To render real tenant data, point the `--data` flag at your own JSON document, for example:

```bash
node bin/export-report \
  --data /tmp/my-report.json \
  --out out/tenant-2024-09.pdf \
  --png out/tenant-2024-09.png
```

Ensure the payload matches the shape expected by `examples/data.sample.json`. Keep custom payloads out of the repository—store them in a secure blob or generate them on demand from the data warehouse.

Application-generated payloads and artifacts contain aggregate report metrics only. Export logs
may contain tenant/job identifiers, format, status, and duration, but never exported row content.
