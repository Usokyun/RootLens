import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const vite = fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url))
const backend = fileURLToPath(new URL('./backend.mjs', import.meta.url))
const python = fileURLToPath(new URL(`../backend/.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`, import.meta.url))
if (!existsSync(vite) || !existsSync(python)) {
  console.error('Install dependencies first: npm ci && (cd backend && uv sync --extra dev --frozen)')
  process.exit(1)
}

const port = process.env.ROOTLENS_WEB_PORT || '5174'
console.log(`RootLens frontend: http://127.0.0.1:${port}; API: http://127.0.0.1:${process.env.ROOTLENS_API_PORT || '8000'}`)
console.log('Databases must already be running. Check them with: npm run backend:check')
const children = [
  spawn(process.execPath, [backend, 'serve'], { cwd: root, stdio: ['ignore', 'inherit', 'inherit'] }),
  spawn(process.execPath, [vite, '--host', '127.0.0.1', '--port', port, '--strictPort'], { cwd: root, stdio: ['ignore', 'inherit', 'inherit'] }),
]
let stopping = false
function stop(code) {
  if (stopping) return
  stopping = true
  process.exitCode = code
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM')
  }
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop(0))
for (const child of children) {
  child.on('error', (error) => {
    console.error(error.message)
    stop(1)
  })
  child.on('exit', (code, signal) => stop(code ?? (signal === 'SIGINT' ? 0 : 1)))
}
