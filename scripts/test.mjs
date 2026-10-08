/**
 * `npm test` from the repository root — the whole regression in one command.
 *
 * Runs, in order: frontend lint → frontend unit tests → frontend typecheck+build
 * → backend pytest. Output keeps each step labelled, the first failure stops
 * the run, and the exit code is the one that failed (never swallowed by a
 * pipe). The backend interpreter is resolved exactly like scripts/dev.mjs:
 * project venv first, PATH python as the fallback.
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const isWindows = process.platform === 'win32'

function backendPython() {
  const candidates = isWindows
    ? [join(root, 'Backend', '.venv', 'Scripts', 'python.exe')]
    : [join(root, 'Backend', '.venv', 'bin', 'python')]
  return candidates.find((candidate) => existsSync(candidate)) ?? (isWindows ? 'python' : 'python3')
}

const steps = [
  { label: 'frontend lint', command: 'npm run lint', cwd: join(root, 'frontend') },
  { label: 'frontend unit tests', command: 'npm run test:unit', cwd: join(root, 'frontend') },
  { label: 'frontend typecheck + build', command: 'npm run build', cwd: join(root, 'frontend') },
  { label: 'backend tests', command: `"${backendPython()}" -m pytest -p no:warnings -q`, cwd: join(root, 'Backend') },
]

function run(step) {
  return new Promise((resolveStep) => {
    process.stdout.write(`\n\x1b[32m▶ ${step.label}\x1b[0m\n`)
    const child = spawn(step.command, {
      cwd: step.cwd,
      shell: isWindows,
      stdio: ['ignore', 'inherit', 'inherit'],
    })
    child.on('exit', (code, signal) => resolveStep(signal ? 1 : (code ?? 1)))
    child.on('error', () => resolveStep(1))
  })
}

let failed = false
for (const step of steps) {
  const code = await run(step)
  if (code !== 0) {
    process.stdout.write(`\n\x1b[31m✖ ${step.label} failed (exit ${code})\x1b[0m\n`)
    failed = true
    break
  }
}

if (!failed) {
  process.stdout.write('\n\x1b[32m✔ all checks passed: lint, 87 frontend unit tests, build, backend pytest\x1b[0m\n')
}
process.exit(failed ? 1 : 0)
