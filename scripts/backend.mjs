import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const backend = fileURLToPath(new URL('../backend/', import.meta.url))
const python = path.join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
if (!existsSync(python)) {
  console.error('Backend environment is missing. Run: cd backend && uv sync --extra dev --frozen')
  process.exit(1)
}

const child = spawn(python, [path.join(backend, 'scripts/dev.py'), ...process.argv.slice(2)], {
  cwd: backend,
  stdio: 'inherit',
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
})
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal))
}
child.on('error', (error) => {
  console.error(`Unable to start backend: ${error.message}`)
  process.exitCode = 1
})
child.on('exit', (code, signal) => {
  process.exitCode = code ?? (signal === 'SIGINT' ? 130 : 1)
})
