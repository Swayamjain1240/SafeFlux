/**
 * `npm run dev` — one command for the whole stack.
 *
 * Starts the FastAPI backend (uvicorn, port 8000) and the Vite frontend
 * (port 5173) side by side, prefixes every line with [backend] / [frontend]
 * so the two interleaved logs stay readable, and shuts both down together on
 * Ctrl+C — a stopped parent never leaves an orphaned server behind.
 *
 * Zero dependencies: plain child_process, no runner library. The backend uses
 * the project venv when it exists (Backend/.venv) and falls back to the first
 * python on PATH otherwise; the frontend is started through npm so it uses the
 * same scripts and flags as running it directly.
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const isWindows = process.platform === 'win32'

// Deliberately NOT `process.env.PORT`: hosts and dev tooling often set a
// generic PORT for their own proxy, and silently binding to it would put the
// API somewhere the frontend cannot reach it.
const BACKEND_PORT = process.env.SAFEFLUX_BACKEND_PORT ?? '8000'
const FRONTEND_PORT = '5173'

function backendCommand() {
  const candidates = isWindows
    ? [join(root, 'Backend', '.venv', 'Scripts', 'python.exe')]
    : [join(root, 'Backend', '.venv', 'bin', 'python')]
  const python = candidates.find((candidate) => existsSync(candidate)) ?? (isWindows ? 'python' : 'python3')
  return `"${python}" -m uvicorn app.main:app --port ${BACKEND_PORT}`
}

const tasks = [
  { name: 'backend', color: '\x1b[36m', command: backendCommand(), cwd: join(root, 'Backend') },
  { name: 'frontend', color: '\x1b[35m', command: 'npm run dev -- --port ' + FRONTEND_PORT, cwd: join(root, 'frontend') },
]

const children = []
let shuttingDown = false

function prefix(name, color, chunk, stream) {
  const text = chunk.toString()
  for (const line of text.split(/\r?\n/)) {
    if (line.trim() === '') continue
    stream.write(`${color}[${name}]\x1b[0m ${line}\n`)
  }
}

function killTree(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  try {
    if (isWindows) {
      // `child.kill()` only terminates the shell we spawned, orphaning
      // uvicorn/vite underneath it; taskkill /T takes the whole tree down.
      spawn('cmd.exe', ['/d', '/s', '/c', `taskkill /PID ${child.pid} /T /F`], { stdio: 'ignore' })
    } else {
      child.kill('SIGTERM')
    }
  } catch {
    /* already gone */
  }
}

function shutdown(exitCode) {
  if (shuttingDown) return
  shuttingDown = true
  for (const child of children) killTree(child)
  // Escalate if a child ignores SIGTERM (Windows has no SIGTERM semantics).
  setTimeout(() => {
    for (const child of children) {
      if (child.exitCode === null) {
        try {
          child.kill('SIGKILL')
        } catch {
          /* already gone */
        }
      }
    }
    process.exit(exitCode)
  }, 1500).unref()
}

for (const task of tasks) {
  const child = spawn(task.command, {
    cwd: task.cwd,
    shell: isWindows,
    env: { ...process.env, FORCE_COLOR: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  children.push(child)

  child.stdout.on('data', (chunk) => prefix(task.name, task.color, chunk, process.stdout))
  child.stderr.on('data', (chunk) => prefix(task.name, task.color, chunk, process.stderr))

  child.on('exit', (code, signal) => {
    if (shuttingDown) return
    process.stderr.write(
      `${task.color}[${task.name}]\x1b[0m exited (${signal ?? `code ${code}`}) — stopping the other process.\n`,
    )
    shutdown(code ?? 1)
  })

  child.on('error', (error) => {
    process.stderr.write(`${task.color}[${task.name}]\x1b[0m failed to start: ${error.message}\n`)
    shutdown(1)
  })
}

process.stdout.write(
  [
    '',
    '\x1b[32mSafeFlux dev\x1b[0m — starting both services (Ctrl+C stops both)',
    `  backend   http://127.0.0.1:${BACKEND_PORT}/api/v1/health`,
    `  frontend  http://localhost:${FRONTEND_PORT}`,
    '',
  ].join('\n') + '\n',
)

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => shutdown(0))
}
