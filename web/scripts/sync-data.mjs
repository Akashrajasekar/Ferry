// Copies the real Ferry run artifacts from the repo root into src/data so the
// site can build from static JSON imports anywhere (including a deploy host
// that only has the web/ folder checked out). Missing sources are logged and
// skipped rather than failing the build.
import { existsSync, mkdirSync, readdirSync, copyFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = join(here, '..');
const repoRoot = join(webRoot, '..');

const destDir = join(webRoot, 'src', 'data');
const destPortsDir = join(destDir, 'ports');
mkdirSync(destDir, { recursive: true });
mkdirSync(destPortsDir, { recursive: true });

function copyFile(srcPath, destPath, label) {
  if (!existsSync(srcPath)) {
    console.warn(`[sync-data] skipping ${label}: not found at ${srcPath}`);
    return;
  }
  copyFileSync(srcPath, destPath);
  console.log(`[sync-data] copied ${label}`);
}

function copyDir(srcDir, destDirPath, label) {
  if (!existsSync(srcDir)) {
    console.warn(`[sync-data] skipping ${label}: not found at ${srcDir}`);
    return;
  }
  for (const entry of readdirSync(srcDir)) {
    if (!entry.endsWith('.json')) continue;
    copyFileSync(join(srcDir, entry), join(destDirPath, entry));
  }
  console.log(`[sync-data] copied ${label}`);
}

try {
  const ferryState = join(repoRoot, 'results', 'ferry-state');

  copyFile(join(ferryState, 'plan.json'), join(destDir, 'plan.json'), 'plan.json');
  copyFile(join(ferryState, 'results.json'), join(destDir, 'results.json'), 'results.json');
  copyFile(join(ferryState, 'audit.json'), join(destDir, 'audit.json'), 'audit.json');
  copyFile(join(ferryState, 'try.json'), join(destDir, 'try.json'), 'try.json');
  copyDir(join(ferryState, 'ports'), destPortsDir, 'ports/*.json');
  copyFile(join(repoRoot, 'metrics.json'), join(destDir, 'metrics.json'), 'metrics.json');

  console.log('[sync-data] done.');
} catch (err) {
  console.warn(`[sync-data] non-fatal error, keeping existing data: ${err.message}`);
}

process.exit(0);
