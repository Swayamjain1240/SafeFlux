/**
 * Digital-twin hero renderer (visual transformation, §10–12).
 *
 * A small, dependency-light Three.js scene: a stylized reactor skid with feed
 * tank, pump, cooling coils, outlet line, a pressure ring and a status beacon.
 * The vessel shell is semi-transparent so the liquid level reads — the twin's
 * job is to look like engineering instrumentation, not a game environment.
 *
 * It is loaded *only* by the landing hero, only after first paint, and it is
 * paused whenever it scrolls out of view or the tab is hidden.
 *
 * Honesty rules from the product spec still apply: this is an illustration of
 * the process *shape*, not a data view. It carries no numbers and claims no
 * state. The only thing it mirrors is the API health probe that the landing
 * page already shows (online → normal, probing → warning, unreachable →
 * critical), and the hero labels it as illustrative.
 *
 * Everything created here is released in `dispose()`; nothing is attached to
 * globals, and there is no per-frame allocation in the loop.
 */

import * as THREE from 'three'

export type TwinStatus = 'normal' | 'warning' | 'critical'

export interface ReactorTwinOptions {
  /** No continuous motion: render on demand only (prefers-reduced-motion). */
  reducedMotion?: boolean
  /** Lower geometry counts, no grid, no particles (narrow viewports). */
  simplified?: boolean
}

export interface ReactorTwinHandle {
  setStatus(status: TwinStatus): void
  /** Start (or resume) the animation loop. */
  start(): void
  /** Stop the loop; the last frame stays on screen. */
  stop(): void
  resize(): void
  dispose(): void
}

const STATUS_COLORS: Record<TwinStatus, number> = {
  normal: 0x00d9ff,
  warning: 0xf59e0b,
  critical: 0xf43f5e,
}

/* Skid geometry, in metres (visual only). */
const VESSEL_RADIUS = 0.72
const VESSEL_BOTTOM = 0.1
const VESSEL_HEIGHT = 2.1
const VESSEL_TOP = VESSEL_BOTTOM + VESSEL_HEIGHT
const LIQUID_LEVEL = 1.15
const OUTLET_Y = 1.72

export function createReactorTwin(
  container: HTMLElement,
  options: ReactorTwinOptions = {},
): ReactorTwinHandle | null {
  const { reducedMotion = false, simplified = false } = options

  let renderer: THREE.WebGLRenderer
  try {
    renderer = new THREE.WebGLRenderer({
      antialias: !simplified,
      alpha: true,
      powerPreference: 'low-power',
    })
  } catch {
    // No WebGL in this environment — the caller keeps its static fallback.
    return null
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, simplified ? 1.25 : 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.15
  renderer.domElement.setAttribute('aria-hidden', 'true')
  renderer.domElement.style.display = 'block'
  renderer.domElement.style.width = '100%'
  renderer.domElement.style.height = '100%'
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100)
  const baseCamera = new THREE.Vector3(3.0, 2.6, 5.1)
  const cameraTarget = new THREE.Vector3(0, 1.52, 0)
  camera.position.copy(baseCamera)

  /* --- shared resources, all disposed at the end ------------------------- */
  const geometries: THREE.BufferGeometry[] = []
  const materials: THREE.Material[] = []
  const track = <T extends THREE.BufferGeometry>(geometry: T): T => {
    geometries.push(geometry)
    return geometry
  }
  const mat = <T extends THREE.Material>(material: T): T => {
    materials.push(material)
    return material
  }

  const segments = simplified ? 20 : 48
  const shellMaterial = mat(
    new THREE.MeshStandardMaterial({
      color: 0x9fd4e6,
      metalness: 0.05,
      roughness: 0.14,
      transparent: true,
      opacity: 0.14,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  )
  const metalMaterial = mat(
    new THREE.MeshStandardMaterial({ color: 0x6c7d90, metalness: 0.9, roughness: 0.32 }),
  )
  const pipeMaterial = mat(
    new THREE.MeshStandardMaterial({ color: 0x596b7e, metalness: 0.88, roughness: 0.35 }),
  )
  const coilMaterial = mat(
    new THREE.MeshStandardMaterial({
      color: 0x7b8ea3,
      metalness: 0.95,
      roughness: 0.22,
      emissive: new THREE.Color(0x0b2e3a),
      emissiveIntensity: 0.7,
    }),
  )
  const liquidMaterial = mat(
    new THREE.MeshStandardMaterial({
      color: 0x0b7f9e,
      metalness: 0.1,
      roughness: 0.2,
      transparent: true,
      opacity: 0.7,
      emissive: new THREE.Color(STATUS_COLORS.normal),
      emissiveIntensity: 0.16,
    }),
  )
  const levelMaterial = mat(
    new THREE.MeshStandardMaterial({
      color: 0x0b0f14,
      metalness: 0.2,
      roughness: 0.3,
      emissive: new THREE.Color(STATUS_COLORS.normal),
      emissiveIntensity: 1.6,
    }),
  )
  const ringMaterial = mat(
    new THREE.MeshStandardMaterial({
      color: 0x2b3b4e,
      metalness: 0.7,
      roughness: 0.3,
      emissive: new THREE.Color(STATUS_COLORS.normal),
      emissiveIntensity: 1.3,
    }),
  )
  const beaconMaterial = mat(
    new THREE.MeshStandardMaterial({
      color: 0x0b0f14,
      emissive: new THREE.Color(STATUS_COLORS.normal),
      emissiveIntensity: 2.6,
      roughness: 0.4,
    }),
  )
  const skidMaterial = mat(
    new THREE.MeshStandardMaterial({ color: 0x121a24, metalness: 0.35, roughness: 0.8 }),
  )

  /* --- skid plate -------------------------------------------------------- */
  const skid = new THREE.Mesh(track(new THREE.BoxGeometry(3.3, 0.07, 1.8)), skidMaterial)
  skid.position.y = 0.035
  scene.add(skid)

  /* --- vessel: glass shell + metal bands + domes ------------------------- */
  const shell = new THREE.Mesh(
    track(new THREE.CylinderGeometry(VESSEL_RADIUS, VESSEL_RADIUS, VESSEL_HEIGHT, segments, 1, true)),
    shellMaterial,
  )
  shell.position.y = VESSEL_BOTTOM + VESSEL_HEIGHT / 2
  scene.add(shell)

  const domeGeometry = track(
    new THREE.SphereGeometry(VESSEL_RADIUS, segments, simplified ? 8 : 16, 0, Math.PI * 2, 0, Math.PI / 2),
  )
  const topDome = new THREE.Mesh(domeGeometry, shellMaterial)
  topDome.position.y = VESSEL_TOP
  scene.add(topDome)

  const bottomDome = new THREE.Mesh(domeGeometry.clone(), shellMaterial)
  geometries.push(bottomDome.geometry)
  bottomDome.rotation.x = Math.PI
  bottomDome.position.y = VESSEL_BOTTOM
  scene.add(bottomDome)

  const bandGeometry = track(new THREE.TorusGeometry(VESSEL_RADIUS + 0.012, 0.035, 8, segments))
  for (const y of [VESSEL_BOTTOM + 0.02, VESSEL_TOP - 0.02]) {
    const band = new THREE.Mesh(bandGeometry, metalMaterial)
    band.rotation.x = Math.PI / 2
    band.position.y = y
    scene.add(band)
  }

  /* --- liquid + level marker -------------------------------------------- */
  const liquid = new THREE.Mesh(
    track(new THREE.CylinderGeometry(VESSEL_RADIUS - 0.05, VESSEL_RADIUS - 0.05, LIQUID_LEVEL, segments)),
    liquidMaterial,
  )
  liquid.position.y = VESSEL_BOTTOM + LIQUID_LEVEL / 2
  scene.add(liquid)

  const levelMarker = new THREE.Mesh(
    track(new THREE.TorusGeometry(VESSEL_RADIUS - 0.04, 0.022, 8, segments)),
    levelMaterial,
  )
  levelMarker.rotation.x = Math.PI / 2
  levelMarker.position.y = VESSEL_BOTTOM + LIQUID_LEVEL
  scene.add(levelMarker)

  /* --- cooling coils ----------------------------------------------------- */
  const coilRings = simplified ? 2 : 3
  const coilGeometry = track(
    new THREE.TorusGeometry(VESSEL_RADIUS + 0.075, 0.028, 8, simplified ? 24 : 56),
  )
  for (let index = 0; index < coilRings; index += 1) {
    const coil = new THREE.Mesh(coilGeometry, coilMaterial)
    coil.rotation.x = Math.PI / 2
    coil.position.y = 0.62 + index * 0.55
    scene.add(coil)
  }

  /* --- pressure ring: two thin arcs above the shoulder ------------------- */
  const pressureRings: THREE.Mesh[] = []
  const ringRadii = [0.95, 1.04]
  for (let index = 0; index < ringRadii.length; index += 1) {
    const ring = new THREE.Mesh(
      track(new THREE.TorusGeometry(ringRadii[index], 0.013, 6, simplified ? 28 : 64, Math.PI * 1.5)),
      ringMaterial,
    )
    ring.rotation.x = Math.PI / 2
    ring.position.y = VESSEL_TOP + 0.22 + index * 0.1
    scene.add(ring)
    pressureRings.push(ring)
  }

  /* --- feed line: tank → pump → vessel ---------------------------------- */
  const tank = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.33, 0.33, 0.92, segments)),
    metalMaterial,
  )
  tank.position.set(-1.72, VESSEL_BOTTOM + 0.46, 0.33)
  scene.add(tank)

  const tankCap = new THREE.Mesh(track(new THREE.TorusGeometry(0.33, 0.03, 8, segments)), metalMaterial)
  tankCap.rotation.x = Math.PI / 2
  tankCap.position.set(-1.72, VESSEL_BOTTOM + 0.92, 0.33)
  scene.add(tankCap)

  const pump = new THREE.Mesh(track(new THREE.BoxGeometry(0.4, 0.34, 0.34)), pipeMaterial)
  pump.position.set(-0.98, 0.24, 0.33)
  scene.add(pump)

  const pumpMotor = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.12, 0.12, 0.26, simplified ? 12 : 24)),
    metalMaterial,
  )
  pumpMotor.rotation.z = Math.PI / 2
  pumpMotor.position.set(-0.64, 0.24, 0.33)
  scene.add(pumpMotor)

  const feedPipe = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.05, 0.05, 0.72, 16)),
    pipeMaterial,
  )
  feedPipe.rotation.z = Math.PI / 2
  feedPipe.position.set(-1.36, 0.31, 0.33)
  scene.add(feedPipe)

  const feedInlet = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.05, 0.05, 0.62, 16)),
    pipeMaterial,
  )
  feedInlet.rotation.z = Math.PI / 2
  feedInlet.position.set(-0.36, 0.24, 0.33)
  scene.add(feedInlet)

  const feedElbow = new THREE.Mesh(track(new THREE.SphereGeometry(0.055, 12, 8)), pipeMaterial)
  feedElbow.position.set(-0.72, 0.24, 0.33)
  scene.add(feedElbow)

  /* --- outlet line ------------------------------------------------------ */
  const outletPipe = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.055, 0.055, 1.05, 16)),
    pipeMaterial,
  )
  outletPipe.rotation.z = Math.PI / 2
  outletPipe.position.set(1.28, OUTLET_Y, -0.3)
  scene.add(outletPipe)

  const outletDrop = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.055, 0.055, 1.15, 16)),
    pipeMaterial,
  )
  outletDrop.position.set(1.8, OUTLET_Y - 0.58, -0.3)
  scene.add(outletDrop)

  const valve = new THREE.Mesh(track(new THREE.BoxGeometry(0.22, 0.22, 0.22)), metalMaterial)
  valve.position.set(1.28, OUTLET_Y, -0.3)
  scene.add(valve)

  const outletStub = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.055, 0.055, 0.5, 16)),
    pipeMaterial,
  )
  outletStub.rotation.z = Math.PI / 2
  outletStub.position.set(0.9, OUTLET_Y, -0.3)
  scene.add(outletStub)

  /* --- flow particles ---------------------------------------------------- */
  const particleCount = simplified ? 4 : 10
  const particleGeometry = track(new THREE.SphereGeometry(0.032, 8, 8))
  const particleMaterial = mat(
    new THREE.MeshBasicMaterial({ color: STATUS_COLORS.normal, transparent: true, opacity: 0.85 }),
  )
  const particles: THREE.Mesh[] = []
  for (let index = 0; index < particleCount; index += 1) {
    const particle = new THREE.Mesh(particleGeometry, particleMaterial)
    scene.add(particle)
    particles.push(particle)
  }

  /* --- status beacon ----------------------------------------------------- */
  const beacon = new THREE.Mesh(track(new THREE.SphereGeometry(0.07, 14, 10)), beaconMaterial)
  beacon.position.set(0, VESSEL_TOP + 0.62, 0)
  scene.add(beacon)
  const beaconLight = new THREE.PointLight(STATUS_COLORS.normal, 7, 4.5, 2)
  beaconLight.position.copy(beacon.position)
  scene.add(beaconLight)

  /* --- lighting ---------------------------------------------------------- */
  scene.add(new THREE.HemisphereLight(0x35597a, 0x04070b, 1.45))
  const key = new THREE.DirectionalLight(0xe6f6ff, 3.1)
  key.position.set(4.2, 6.2, 5)
  scene.add(key)
  const rim = new THREE.DirectionalLight(0x00d9ff, 2.4)
  rim.position.set(-5, 3.2, -4)
  scene.add(rim)
  const fill = new THREE.DirectionalLight(0x8b5cf6, 1.1)
  fill.position.set(-2, 1.2, 5)
  scene.add(fill)
  const heat = new THREE.PointLight(0xf59e0b, 1.6, 3.6, 2)
  heat.position.set(0, VESSEL_BOTTOM + 0.4, 0)
  scene.add(heat)

  if (!simplified) {
    const grid = new THREE.GridHelper(10, 10, 0x213043, 0x151d28)
    const gridMaterial = grid.material as THREE.Material
    gridMaterial.transparent = true
    gridMaterial.opacity = 0.4
    materials.push(gridMaterial)
    geometries.push(grid.geometry)
    grid.position.y = 0
    scene.add(grid)
  }

  /* --- state ------------------------------------------------------------- */
  const statusColor = new THREE.Color(STATUS_COLORS.normal)
  const targetColor = new THREE.Color(STATUS_COLORS.normal)
  let status: TwinStatus = 'normal'
  let particleSpeed = 1.1
  let frame = 0
  let running = false
  let disposed = false
  // Hand-rolled clock: `THREE.Clock` is deprecated upstream, and we only need
  // a monotonic delta plus total elapsed time (seconds).
  let lastStamp = 0
  let elapsedTime = 0
  const pointerTarget = { x: 0, y: 0 }

  function stamp(): number {
    return (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000
  }

  function handlePointerMove(event: PointerEvent) {
    const rect = container.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    pointerTarget.x = THREE.MathUtils.clamp(((event.clientX - rect.left) / rect.width) * 2 - 1, -1, 1)
    pointerTarget.y = THREE.MathUtils.clamp(((event.clientY - rect.top) / rect.height) * 2 - 1, -1, 1)
  }

  function applyStatusStyles() {
    const critical = status === 'critical'
    const warning = status === 'warning'
    const color = STATUS_COLORS[status]
    ringMaterial.emissiveIntensity = critical ? 2.6 : warning ? 1.9 : 1.3
    levelMaterial.emissiveIntensity = critical ? 2.6 : warning ? 2 : 1.6
    beaconMaterial.emissiveIntensity = critical ? 4 : warning ? 3.2 : 2.6
    liquidMaterial.emissive.setHex(color)
    liquidMaterial.emissiveIntensity = critical ? 0.42 : warning ? 0.3 : 0.16
    heat.intensity = critical ? 5.5 : warning ? 3 : 1.6
    particleMaterial.color.setHex(color)
    particleSpeed = critical ? 3.1 : warning ? 1.9 : 1.1
  }

  function placeFeedParticle(particle: THREE.Mesh, u: number) {
    if (u < 0.45) {
      const v = u / 0.45
      particle.position.set(-1.72 + v * 0.36, 0.31, 0.33)
    } else {
      const v = (u - 0.45) / 0.55
      particle.position.set(-1.36 + v * 1.0, 0.28 - v * 0.04, 0.33)
    }
  }

  function placeOutletParticle(particle: THREE.Mesh, u: number) {
    if (u < 0.6) {
      const v = u / 0.6
      particle.position.set(0.65 + v * 1.15, OUTLET_Y, -0.3)
    } else {
      const v = (u - 0.6) / 0.4
      particle.position.set(1.8, OUTLET_Y - v * 1.15, -0.3)
    }
  }

  function renderFrame(delta: number, elapsed: number) {
    statusColor.lerp(targetColor, Math.min(1, delta * 4))
    ringMaterial.emissive.copy(statusColor)
    levelMaterial.emissive.copy(statusColor)
    beaconMaterial.emissive.copy(statusColor)
    beaconLight.color.copy(statusColor)

    // Parallax only: the camera eases toward the pointer and never orbits.
    camera.position.x += (baseCamera.x + pointerTarget.x * 0.45 - camera.position.x) * Math.min(1, delta * 2.2)
    camera.position.y += (baseCamera.y - pointerTarget.y * 0.26 - camera.position.y) * Math.min(1, delta * 2.2)
    camera.lookAt(cameraTarget)

    const critical = status === 'critical'
    const pulse = critical ? 1 + Math.sin(elapsed * 7) * 0.03 : 1 + Math.sin(elapsed * 1.5) * 0.008

    for (let index = 0; index < pressureRings.length; index += 1) {
      const ring = pressureRings[index]
      ring.rotation.z = elapsed * (critical ? 0.5 : 0.2) + index * 1.2
      ring.scale.setScalar(pulse + index * 0.012)
    }

    const level = LIQUID_LEVEL + Math.sin(elapsed * 0.5) * 0.03
    liquid.scale.y = level / LIQUID_LEVEL
    liquid.position.y = VESSEL_BOTTOM + level / 2
    levelMarker.position.y = VESSEL_BOTTOM + level

    beacon.scale.setScalar(critical ? pulse : 1)
    beaconLight.intensity = 7 + (critical ? Math.sin(elapsed * 7) * 2.6 : 0)

    // Particles run feed → vessel and vessel → outlet, then wrap. Positions are
    // written in place: no per-frame object allocation.
    const advance = elapsed * particleSpeed
    for (let index = 0; index < particles.length; index += 1) {
      const particle = particles[index]
      const t = (advance * 0.2 + index / particles.length) % 1
      if (index % 2 === 0) placeFeedParticle(particle, t)
      else placeOutletParticle(particle, t)
    }

    renderer.render(scene, camera)
  }

  function loop() {
    if (!running || disposed) return
    frame = requestAnimationFrame(loop)
    const at = stamp()
    const delta = Math.min(Math.max(at - lastStamp, 0), 0.05)
    lastStamp = at
    elapsedTime += delta
    renderFrame(delta, elapsedTime)
  }

  function start() {
    if (disposed || running) return
    if (reducedMotion) {
      // Reduced motion: one representative frame, re-rendered on state/size
      // change instead of a continuous loop.
      renderFrame(0.016, 0)
      return
    }
    running = true
    lastStamp = stamp()
    frame = requestAnimationFrame(loop)
  }

  function stop() {
    running = false
    if (frame) cancelAnimationFrame(frame)
    frame = 0
  }

  function resize() {
    const width = container.clientWidth
    const height = container.clientHeight
    if (width === 0 || height === 0) return
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    if (!running) renderFrame(0.016, elapsedTime)
  }

  function setStatus(next: TwinStatus) {
    if (next === status) return
    status = next
    targetColor.setHex(STATUS_COLORS[next])
    applyStatusStyles()
    if (!running) renderFrame(0.016, elapsedTime)
  }

  function dispose() {
    if (disposed) return
    disposed = true
    stop()
    container.removeEventListener('pointermove', handlePointerMove)
    for (const geometry of geometries) geometry.dispose()
    for (const material of materials) material.dispose()
    scene.clear()
    renderer.dispose()
    const canvas = renderer.domElement
    if (canvas.parentNode) canvas.parentNode.removeChild(canvas)
  }

  if (!reducedMotion) container.addEventListener('pointermove', handlePointerMove, { passive: true })

  applyStatusStyles()
  resize()

  return { setStatus, start, stop, resize, dispose }
}
