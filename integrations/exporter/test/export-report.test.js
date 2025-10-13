const path = require('node:path');
const assert = require('node:assert/strict');
const test = require('node:test');

const exporterPath = path.join(__dirname, '..', 'bin', 'export-report');
const browserModulePath = path.join(__dirname, '..', 'lib', 'browser');
const canvaModulePath = path.join(__dirname, '..', 'lib', 'canva');
const renderReportModulePath = path.join(__dirname, '..', 'lib', 'renderReport');

test('run resolves default PNG path when --png has no value', async (t) => {
  delete require.cache[exporterPath];

  const browserModule = require(browserModulePath);
  const originalRenderToFiles = browserModule.renderToFiles;
  const canvaModule = require(canvaModulePath);
  const originalExportDesignStub = canvaModule.exportDesignStub;
  const renderReportModule = require(renderReportModulePath);
  const originalRenderReport = renderReportModule.renderReport;

  let receivedOptions;

  browserModule.renderToFiles = async (_html, options) => {
    receivedOptions = options;
  };

  canvaModule.exportDesignStub = async () => {};
  renderReportModule.renderReport = async () => '<html></html>';

  t.after(() => {
    browserModule.renderToFiles = originalRenderToFiles;
    canvaModule.exportDesignStub = originalExportDesignStub;
    renderReportModule.renderReport = originalRenderReport;
    delete require.cache[exporterPath];
  });

  const exporter = require(exporterPath);
  const defaultPngPath = path.join(__dirname, '..', 'out', 'report.png');

  await exporter.run(['--png']);

  assert.equal(receivedOptions.pngPath, defaultPngPath);
});
