import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();
const frontendSrc = path.join(repoRoot, 'frontend', 'src');
const routerPath = path.join(frontendSrc, 'router.tsx');

const failures = [];

function recordFailure(message) {
  failures.push(message);
}

function runRg(pattern, target, extraArgs = []) {
  try {
    return execFileSync('rg', ['-n', pattern, target, ...extraArgs], {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  } catch (error) {
    if (error.status === 1) {
      return '';
    }
    throw error;
  }
}

function assertAbsent(pattern, target, description, extraArgs = []) {
  const matches = runRg(pattern, target, extraArgs);
  if (matches) {
    recordFailure(`${description}\n${matches}`);
  }
}

function assertMissing(relPath) {
  const absolutePath = path.join(repoRoot, relPath);
  if (existsSync(absolutePath)) {
    recordFailure(`Deleted surface restored unexpectedly: ${relPath}`);
  }
}

function checkRouter() {
  const source = readFileSync(routerPath, 'utf8');
  const lazyImportPattern = /lazy\(\(\) => import\('([^']+)'\)\)/g;
  let match;
  while ((match = lazyImportPattern.exec(source)) !== null) {
    const importPath = match[1];
    const resolvedBase = path.resolve(path.dirname(routerPath), importPath);
    const candidates = [
      `${resolvedBase}.tsx`,
      `${resolvedBase}.ts`,
      path.join(resolvedBase, 'index.tsx'),
      path.join(resolvedBase, 'index.ts'),
    ];
    if (!candidates.some((candidate) => existsSync(candidate))) {
      recordFailure(`Router lazy import does not resolve: ${importPath}`);
    }
  }

  const catchAllIndex = source.lastIndexOf("path: '*'");
  if (catchAllIndex === -1) {
    recordFailure("Router catch-all '*' route is missing.");
  }
  const lastProtectedRouteIndex = source.lastIndexOf("path: '/dashboards'");
  if (catchAllIndex !== -1 && catchAllIndex < lastProtectedRouteIndex) {
    recordFailure("Router catch-all '*' route is not last.");
  }

  const alertsNewIndex = source.indexOf("path: '/alerts/new'");
  const alertsHistoryIndex = source.indexOf("path: '/alerts/history'");
  const alertsDetailIndex = source.indexOf("path: '/alerts/:alertId'");
  if (
    alertsNewIndex === -1 ||
    alertsHistoryIndex === -1 ||
    alertsDetailIndex === -1 ||
    alertsNewIndex > alertsDetailIndex ||
    alertsHistoryIndex > alertsDetailIndex
  ) {
    recordFailure('Alert route ordering is invalid in router.tsx.');
  }
}

assertAbsent(String.raw`\.\./state/useToastStore`, frontendSrc, 'Found deprecated toast store import path.');
assertAbsent(String.raw`\bpushToast\b`, frontendSrc, 'Found deprecated pushToast usage.');
assertAbsent(
  String.raw`import\s+useToastStore\s+from\s+['"][^'"]*useToastStore['"]`,
  frontendSrc,
  'Found default import of useToastStore.',
  ['-P'],
);
assertAbsent(String.raw`\bToastProvider\b`, frontendSrc, 'Found deleted ToastProvider reference.');
assertAbsent(String.raw`\bToastViewport\b`, frontendSrc, 'Found deleted ToastViewport reference.');
assertAbsent(
  String.raw`addToast\s*\(\s*\{[\s\S]*?tone\s*:`,
  frontendSrc,
  'Found addToast object-argument usage.',
  ['-P', '-U'],
);
assertAbsent(String.raw`\bas any\b`, path.join(frontendSrc, 'routes'), 'Found `as any` in frontend/src/routes.');

assertMissing('frontend/src/state/useToastStore.ts');
assertMissing('frontend/src/components/ToastProvider.tsx');
assertMissing('frontend/src/components/ToastViewport.tsx');

checkRouter();

if (failures.length > 0) {
  console.error('Frontend guardrail check failed.\n');
  for (const failure of failures) {
    console.error(`- ${failure}\n`);
  }
  process.exit(1);
}

console.log('Frontend guardrail check passed.');
