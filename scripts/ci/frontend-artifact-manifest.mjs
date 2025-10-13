import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const scriptPath = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(scriptPath), '..', '..');
const frontendDir = path.join(repoRoot, 'frontend');
const distDir = path.join(frontendDir, 'dist');
const distZipPath = path.join(frontendDir, 'frontend-dist.zip');
const coverageDir = path.join(frontendDir, 'coverage');
const coverageSummaryPath = path.join(coverageDir, 'coverage-summary.json');
const vitestReportPath = path.join(frontendDir, 'test-results', 'vitest-report.json');
const manifestPath = path.join(frontendDir, 'frontend-ci-artifacts.json');

async function readJsonIfExists(targetPath) {
  try {
    const raw = await fs.readFile(targetPath, 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

async function statIfExists(targetPath) {
  try {
    return await fs.stat(targetPath);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

async function getDirectorySize(targetPath) {
  const stats = await statIfExists(targetPath);
  if (!stats) {
    return 0;
  }

  if (stats.isFile()) {
    return stats.size;
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

function toNumberOrNull(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

async function main() {
  const distDirSize = await getDirectorySize(distDir);
  const distZipStats = await statIfExists(distZipPath);
  const coverageDirSize = await getDirectorySize(coverageDir);
  const coverageSummary = await readJsonIfExists(coverageSummaryPath);
  const vitestReport = await readJsonIfExists(vitestReportPath);

  const manifest = {
    version: 1,
    generatedAt: new Date().toISOString(),
    commit: process.env.GITHUB_SHA ?? null,
    artifactBundle: {
      name: 'frontend-ci-artifacts',
      entries: [],
    },
    metrics: {
      dist: {
        uncompressedBytes: distDirSize || null,
        zipBytes: distZipStats?.size ?? null,
      },
      coverage: coverageSummary?.total ?? null,
      tests: {
        total: toNumberOrNull(vitestReport?.numTotalTests),
        passed: toNumberOrNull(vitestReport?.numPassedTests),
        failed: toNumberOrNull(vitestReport?.numFailedTests),
      },
    },
  };

  if (distZipStats) {
    manifest.artifactBundle.entries.push({
      path: 'frontend-dist.zip',
      type: 'file',
      sizeBytes: distZipStats.size,
      source: 'frontend/dist',
    });
  }

  if (coverageDirSize > 0) {
    manifest.artifactBundle.entries.push({
      path: 'coverage/',
      type: 'directory',
      sizeBytes: coverageDirSize,
    });
  }

  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  console.log(`Wrote frontend artifact manifest to ${path.relative(repoRoot, manifestPath)}`);
}

main().catch((error) => {
  console.error('frontend-artifact-manifest failed:', error);
  process.exitCode = 1;
});
