import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptPath = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(scriptPath), '..', '..');
const frontendDir = path.join(repoRoot, 'frontend');
const coverageSummaryPath = path.join(frontendDir, 'coverage', 'coverage-summary.json');
const vitestReportPath = path.join(frontendDir, 'test-results', 'vitest-report.json');
const distDir = path.join(frontendDir, 'dist');

async function readJsonIfExists(filePath) {
  try {
    const raw = await fs.readFile(filePath, 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

async function getDirectorySize(targetPath) {
  try {
    const stats = await fs.stat(targetPath);
    if (!stats.isDirectory()) {
      return stats.size;
    }
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return 0;
    }
    throw error;
  }

  let total = 0;
  const entries = await fs.readdir(targetPath, { withFileTypes: true });
  for (const entry of entries) {
    const entryPath = path.join(targetPath, entry.name);
    if (entry.isDirectory()) {
      total += await getDirectorySize(entryPath);
    } else if (entry.isFile()) {
      const entryStats = await fs.stat(entryPath);
      total += entryStats.size;
    }
  }
  return total;
}

function formatBytes(bytes) {
  if (bytes === 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

async function main() {
  const coverageSummary = await readJsonIfExists(coverageSummaryPath);
  const vitestReport = await readJsonIfExists(vitestReportPath);
  const distSizeBytes = await getDirectorySize(distDir);

  const totalTests = vitestReport?.numTotalTests;
  const passedTests = vitestReport?.numPassedTests;
  const failedTests = vitestReport?.numFailedTests;
  const coveragePct = coverageSummary?.total?.lines?.pct;
  const buildSize = formatBytes(distSizeBytes);

  const testsLine =
    totalTests != null && passedTests != null && failedTests != null
      ? `- **Tests:** ${passedTests}/${totalTests} passed (${failedTests} failed)`
      : '- **Tests:** not available';
  const coverageLine =
    coveragePct != null
      ? `- **Line Coverage:** ${Number.parseFloat(coveragePct).toFixed(2)}%`
      : '- **Line Coverage:** not available';

  const summaryLines = [
    '## Frontend Coverage Summary',
    '',
    testsLine,
    coverageLine,
    `- **Build Artifact Size:** ${buildSize}`,
  ];

  const summaryContent = summaryLines.join('\n');
  const stepSummaryPath = process.env.GITHUB_STEP_SUMMARY;

  if (stepSummaryPath) {
    await fs.appendFile(stepSummaryPath, `${summaryContent}\n`);
  } else {
    console.log(summaryContent);
  }
}

main().catch((error) => {
  console.error('coverage-summary-helper failed:', error);
  process.exitCode = 1;
});
