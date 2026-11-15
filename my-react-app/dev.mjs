// MusicHub dev launcher: `npm run dev` starts BOTH the Python backend and the Vite dev server.
// If a backend is already running on :8000 it is reused, not spawned twice.
import { spawn, execFile } from 'node:child_process';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const backend = path.join(root, 'backend');

const log = (tag, msg) => console.log(`[${tag}] ${msg}`);

const portFree = (port) => new Promise((resolve) => {
  const s = net.connect({ port }, () => { s.destroy(); resolve(false); });
  s.on('error', () => { s.destroy(); resolve(true); });
  s.setTimeout(500, () => { s.destroy(); resolve(true); });
});

const pythonCandidates = [
  path.join(root, 'build-env', 'Scripts', 'python.exe'),
  path.join(backend, 'env', 'Scripts', 'python.exe'),
  path.join(backend, 'venv', 'Scripts', 'python.exe'),
];
const findPython = () => pythonCandidates.find((p) => fs.existsSync(p));

const killTree = (pid) => {
  if (process.platform === 'win32') {
    execFile('taskkill', ['/pid', String(pid), '/T', '/F'], () => {});
  } else {
    try { process.kill(-pid); } catch { /* already gone */ }
  }
};

const children = [];
const cleanup = () => { for (const c of children) { try { c.kill(); } catch {} } killTree(process.pid); };
process.on('SIGINT', () => { cleanup(); process.exit(0); });
process.on('SIGTERM', () => { cleanup(); process.exit(0); });
process.on('exit', cleanup);

async function main() {
  if (!fs.existsSync(path.join(here, 'node_modules'))) {
    log('vite', 'node_modules missing — running npm install first (one time)…');
    await new Promise((res) => spawn('npm.cmd', ['install'], { cwd: here, stdio: 'inherit', shell: true })
      .on('exit', res));
  }

  const busy = !(await portFree(8000));
  if (busy) {
    log('backend', 'port 8000 already serving a MusicHub backend — reusing it.');
  } else {
    const python = findPython();
    if (!python) {
      log('backend', '❌ No backend Python found. Create one: python -m venv backend/env && '
        + 'backend/env/Scripts/pip install -r backend/requirements.txt (then restart).');
      log('backend', 'Continuing with the frontend only.');
    } else {
      log('backend', `starting ${python}`);
      const be = spawn(python, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000', '--reload'], {
        cwd: backend, stdio: 'inherit', env: { ...process.env, PYTHONUTF8: '1' },
      });
      children.push(be);
    }
  }

  const vite = spawn(process.execPath, [path.join(here, 'node_modules', 'vite', 'bin', 'vite.js')], {
    cwd: here, stdio: 'inherit',
  });
  children.push(vite);
  vite.on('exit', (code) => { cleanup(); process.exit(code ?? 0); });
}

main();
