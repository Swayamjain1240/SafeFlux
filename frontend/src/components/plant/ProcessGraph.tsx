import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useProcessMotion } from '../../animation/useProcessMotion'
import type { SafetyStatus } from '../../animation/motion'
import { chooseGraphOrientation, type GraphOrientation } from '../../layout/graphLayout'
import type { PlantDetail } from '../../types/plant'

/**
 * Animated process graph for the locked MVP process (Part 6):
 *
 *   Feed Tank → Pump P-101 → Heated Reactor R-101 → Outlet Valve V-101 → Product Tank
 *   with Heater, Cooling and Sensors attached to the reactor.
 *
 * Live values come from a telemetry frame when one exists, otherwise from the
 * configured plant — never invented. GSAP animates only what means something:
 * pipeline flow, the pump rotor, a warning/critical pulse and the state-change
 * flash. `prefers-reduced-motion` renders everything static.
 */

export type Tone = 'ok' | 'warn' | 'crit' | 'idle'

export interface ProcessSnapshot {
  temperature_c: number
  pressure_bar: number
  level_pct: number
  feed_flow_lpm: number
  outlet_flow_lpm: number
  pump_running: boolean
}

type UnitNodeData = {
  title: string
  subtitle: string
  detail: string
  tone: Tone
  rotor?: boolean
  pulse?: boolean
  flash?: boolean
}

type UnitNode = Node<UnitNodeData, 'unit'>

const CARD_TONE: Record<Tone, string> = {
  ok: 'border-safe/45 bg-safe/5',
  warn: 'border-warn/50 bg-warn/8',
  crit: 'border-crit/55 bg-crit/10',
  idle: 'border-edge-strong bg-surface/85',
}

const DOT_TONE: Record<Tone, string> = {
  ok: 'bg-safe',
  warn: 'bg-warn',
  crit: 'bg-crit',
  idle: 'bg-slate-500',
}

const PULSE_TONE: Record<Tone, string> = {
  ok: 'border-safe/70',
  warn: 'border-warn',
  crit: 'border-crit',
  idle: 'border-edge-strong',
}

// Narrower cards and a shorter pitch keep the whole line legible when it has to
// share a two-column workspace (e.g. 1366×768) instead of being clipped.
const NODE_WIDTH = 'w-40'
const X_STEP = 200

/**
 * The five-stage line is wide (≈960px), so a half-width workspace column needs
 * a scale below React Flow's default 0.5 floor to fit. Allow it — being clipped
 * is worse than being small, and the zoom controls are always available.
 */
const MIN_ZOOM = 0.28
const FIT_VIEW = { padding: 0.1, minZoom: MIN_ZOOM } as const

const UnitNodeComponent = memo(function UnitNodeComponent({ data }: NodeProps<UnitNode>) {
  return (
    <div className={`relative ${NODE_WIDTH}`}>
      {/* Explicit handle ids so the utility edges (heater/cooling/sensors)
          can attach to the top/bottom while the process line uses left/right. */}
      <Handle type="target" id="left" position={Position.Left} className="!bg-accent/80" />
      <Handle type="source" id="right" position={Position.Right} className="!bg-accent/80" />
      <Handle type="target" id="top" position={Position.Top} className="!bg-accent/80" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="!bg-accent/80" />
      <div
        data-sf-state={data.flash ? '' : undefined}
        className={`relative rounded-md border px-3 py-2 text-left shadow-lg ${CARD_TONE[data.tone]}`}
      >
        {data.pulse && (
          <span
            data-sf-pulse=""
            aria-hidden="true"
            className={`pointer-events-none absolute -inset-px rounded-md border ${PULSE_TONE[data.tone]}`}
          />
        )}
        <div className="relative flex items-center gap-2">
          <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${DOT_TONE[data.tone]}`} />
          <p className="truncate text-xs font-semibold text-slate-100">{data.title}</p>
          {data.rotor && (
            <span
              data-sf-rotor=""
              aria-hidden="true"
              className="ml-auto h-3 w-3 shrink-0 rounded-full border-2 border-dashed border-safe/80"
            />
          )}
        </div>
        <p className="relative mt-1 text-[10px] tracking-wide text-slate-400 uppercase">{data.subtitle}</p>
        <p className="stat-num relative text-[11px] text-accent">{data.detail}</p>
      </div>
    </div>
  )
})

const nodeTypes = { unit: UnitNodeComponent }

function clampTone(pumpRunning: boolean, value: number | undefined, limit: number): Tone {
  if (value === undefined) return 'idle'
  if (value > limit) return 'crit'
  if (value >= limit * 0.9) return 'warn'
  if (!pumpRunning) return 'idle'
  return 'ok'
}

/**
 * Node coordinates per orientation. The process line is wide and short, so in a
 * tall/narrow box (tablet, mobile, or a squeezed desktop column) laying it
 * vertically lets React Flow render it far closer to native size instead of
 * shrinking every label past legibility.
 */
function layoutFor(orientation: GraphOrientation): {
  feed: [number, number]
  pump: [number, number]
  reactor: [number, number]
  valve: [number, number]
  product: [number, number]
  heater: [number, number]
  cooling: [number, number]
  sensors: [number, number]
} {
  if (orientation === 'vertical') {
    const y = (index: number) => index * 180
    return {
      feed: [0, y(0)],
      pump: [0, y(1)],
      reactor: [0, y(2)],
      valve: [0, y(3)],
      product: [0, y(4)],
      sensors: [260, y(1)],
      heater: [260, y(2)],
      cooling: [260, y(3)],
    }
  }
  const x = (index: number) => index * X_STEP
  return {
    feed: [0, 70],
    pump: [x(1), 70],
    reactor: [x(2), 70],
    valve: [x(3), 70],
    product: [x(4), 70],
    heater: [x(1.4), -80],
    cooling: [x(2.6), -80],
    sensors: [x(2.6), 220],
  }
}

function buildGraph(
  plant: PlantDetail,
  values: ProcessSnapshot,
  safetyStatus: SafetyStatus,
  orientation: GraphOrientation,
): { nodes: UnitNode[]; edges: Edge[] } {
  const { config, safety_limits: limits } = plant
  const at = layoutFor(orientation)
  const pumpRunning = values.pump_running
  const reactorTone: Tone =
    safetyStatus === 'violation' ? 'crit' : safetyStatus === 'safe' ? 'ok' : safetyStatus === 'unknown' ? 'idle' : 'warn'

  const nodes: UnitNode[] = [
    {
      id: 'feed',
      type: 'unit',
      position: { x: at.feed[0], y: at.feed[1] },
      data: {
        title: 'Feed Tank',
        subtitle: 'Raw feed',
        detail: `Feed ${values.feed_flow_lpm.toFixed(0)} L/min`,
        tone: clampTone(pumpRunning, values.level_pct, limits.max_level_pct),
      },
    },
    {
      id: 'pump',
      type: 'unit',
      position: { x: at.pump[0], y: at.pump[1] },
      data: {
        title: 'Pump P-101',
        subtitle: 'Feed pump',
        detail: pumpRunning ? 'Running' : 'Stopped',
        tone: pumpRunning ? 'ok' : 'idle',
        rotor: true,
      },
    },
    {
      id: 'reactor',
      type: 'unit',
      position: { x: at.reactor[0], y: at.reactor[1] },
      data: {
        title: 'Heated Reactor R-101',
        subtitle: 'Heater · Cooling · Sensors',
        detail: `${values.temperature_c.toFixed(1)} °C · ${values.pressure_bar.toFixed(2)} bar`,
        tone: reactorTone,
        pulse: true,
        flash: true,
      },
    },
    {
      id: 'valve',
      type: 'unit',
      position: { x: at.valve[0], y: at.valve[1] },
      data: {
        title: 'Outlet Valve V-101',
        subtitle: 'Discharge control',
        detail: `${config.valve_position_pct.toFixed(0)}% open · ${values.outlet_flow_lpm.toFixed(0)} L/min`,
        tone: pumpRunning ? 'ok' : 'idle',
      },
    },
    {
      id: 'product',
      type: 'unit',
      position: { x: at.product[0], y: at.product[1] },
      data: {
        title: 'Product Tank',
        subtitle: 'Discharge',
        detail: `Level ${values.level_pct.toFixed(1)}%`,
        tone: clampTone(pumpRunning, values.level_pct, limits.max_level_pct),
      },
    },
    {
      id: 'heater',
      type: 'unit',
      position: { x: at.heater[0], y: at.heater[1] },
      data: {
        title: 'Heater',
        subtitle: 'Heating',
        detail: `${config.heater_power_pct.toFixed(0)}% duty`,
        tone: 'ok',
      },
    },
    {
      id: 'cooling',
      type: 'unit',
      position: { x: at.cooling[0], y: at.cooling[1] },
      data: {
        title: 'Cooling Jacket',
        subtitle: 'Cooling',
        detail: `${config.cooling_pct.toFixed(0)}% duty`,
        tone: config.cooling_pct <= 0 ? 'crit' : config.cooling_pct < 50 ? 'warn' : 'ok',
      },
    },
    {
      id: 'sensors',
      type: 'unit',
      position: { x: at.sensors[0], y: at.sensors[1] },
      data: {
        title: 'Sensors',
        subtitle: 'T · P · L',
        detail: safetyStatus === 'unknown' ? 'Awaiting telemetry' : safetyStatus.replace('_', ' '),
        tone: safetyStatus === 'violation' ? 'crit' : safetyStatus === 'safe' ? 'ok' : safetyStatus === 'unknown' ? 'idle' : 'warn',
      },
    },
  ]

  // The spine always follows the flow direction; the three reactor utilities
  // hang off the opposite axis (above/below when horizontal, right when not).
  const [spineOut, spineIn] = orientation === 'vertical' ? ['bottom', 'top'] : ['right', 'left']
  const utilityHandles =
    orientation === 'vertical'
      ? { sourceHandle: 'right', targetHandle: 'left' }
      : { sourceHandle: 'bottom', targetHandle: 'top' }

  const edges: Edge[] = [
    { id: 'e-feed-pump', source: 'feed', target: 'pump', sourceHandle: spineOut, targetHandle: spineIn, className: 'sf-flow-main' },
    { id: 'e-pump-reactor', source: 'pump', target: 'reactor', sourceHandle: spineOut, targetHandle: spineIn, className: 'sf-flow-main' },
    { id: 'e-reactor-valve', source: 'reactor', target: 'valve', sourceHandle: spineOut, targetHandle: spineIn, className: 'sf-flow-main' },
    { id: 'e-valve-product', source: 'valve', target: 'product', sourceHandle: spineOut, targetHandle: spineIn, className: 'sf-flow-main' },
    { id: 'e-heater-reactor', source: 'heater', target: 'reactor', ...utilityHandles, animated: false },
    { id: 'e-cooling-reactor', source: 'cooling', target: 'reactor', ...utilityHandles, animated: false },
    { id: 'e-reactor-sensors', source: 'reactor', target: 'sensors', ...utilityHandles, animated: false },
  ]

  return { nodes, edges }
}

export interface ProcessGraphProps {
  plant: PlantDetail
  values: ProcessSnapshot
  safetyStatus: SafetyStatus
  reducedMotion: boolean
  className?: string
}

export function ProcessGraph({
  plant,
  values,
  safetyStatus,
  reducedMotion,
  className = '',
}: ProcessGraphProps) {
  const container = useRef<HTMLDivElement | null>(null)
  const [orientation, setOrientation] = useState<GraphOrientation>('horizontal')

  // React Flow caches each node's measured size on the node object, so handing
  // it brand-new objects on every render makes it re-measure forever — and an
  // unmeasured node renders no edges. The monitor re-renders for every streamed
  // frame, so the graph is rebuilt only when a displayed number actually
  // changes, which keeps the node objects (and therefore the edges) stable.
  const {
    temperature_c,
    pressure_bar,
    level_pct,
    feed_flow_lpm,
    outlet_flow_lpm,
    pump_running,
  } = values
  const snapshot = useMemo<ProcessSnapshot>(
    () => ({
      temperature_c,
      pressure_bar,
      level_pct,
      feed_flow_lpm,
      outlet_flow_lpm,
      pump_running,
    }),
    [temperature_c, pressure_bar, level_pct, feed_flow_lpm, outlet_flow_lpm, pump_running],
  )

  const { nodes, edges } = useMemo(
    () => buildGraph(plant, snapshot, safetyStatus, orientation),
    [plant, snapshot, safetyStatus, orientation],
  )
  // React Flow renders edges only after it has measured the nodes, so motion
  // waits for `onInit` instead of starting against (or missing) absent paths.
  const [edgesReady, setEdgesReady] = useState(false)
  const flow = useRef<ReactFlowInstance<UnitNode, Edge> | null>(null)
  const handleInit = useCallback((instance: ReactFlowInstance<UnitNode, Edge>) => {
    flow.current = instance
    instance.fitView(FIT_VIEW)
    setEdgesReady(true)
  }, [])

  // Pick the orientation from the box we are actually given, then keep it in
  // step with resizes: a window/panel change alters the container but React Flow
  // keeps its old transform, which would push the outlet nodes outside the
  // clipped canvas. Re-fitting keeps the whole P&ID visible (never a clipped card).
  useEffect(() => {
    const element = container.current
    if (!element || typeof ResizeObserver === 'undefined') return
    let frame = 0
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect
      if (!box) return
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        setOrientation(chooseGraphOrientation(box.width, box.height))
        flow.current?.fitView(FIT_VIEW)
      })
    })
    observer.observe(element)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [])

  // Re-fit after a layout change commits, so the new coordinates are fitted too.
  useEffect(() => {
    if (edgesReady) flow.current?.fitView(FIT_VIEW)
  }, [orientation, edgesReady])

  useProcessMotion(container, {
    reducedMotion,
    hasTelemetry: safetyStatus !== 'unknown',
    pumpRunning: pump_running,
    safetyStatus,
    stateKey: safetyStatus,
    edgesReady,
    graphKey: orientation,
  })

  return (
    <div
      ref={container}
      className={`overflow-hidden rounded-md border border-edge/80 bg-void/50 ${className}`}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onInit={handleInit}
        fitView
        minZoom={MIN_ZOOM}
        fitViewOptions={FIT_VIEW}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
        preventScrolling={false}
      >
        <Background color="#1e2a38" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
