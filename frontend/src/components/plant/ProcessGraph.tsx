import { memo, useMemo, useRef } from 'react'
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useProcessMotion } from '../../animation/useProcessMotion'
import type { SafetyStatus } from '../../animation/motion'
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
  ok: 'border-emerald-500/45 bg-emerald-500/5',
  warn: 'border-amber-500/55 bg-amber-500/10',
  crit: 'border-rose-500/60 bg-rose-500/10',
  idle: 'border-slate-700 bg-slate-900/80',
}

const DOT_TONE: Record<Tone, string> = {
  ok: 'bg-emerald-400',
  warn: 'bg-amber-400',
  crit: 'bg-rose-500',
  idle: 'bg-slate-500',
}

const PULSE_TONE: Record<Tone, string> = {
  ok: 'border-emerald-400/70',
  warn: 'border-amber-400',
  crit: 'border-rose-500',
  idle: 'border-slate-600',
}

const UnitNodeComponent = memo(function UnitNodeComponent({ data }: NodeProps<UnitNode>) {
  return (
    <div className="relative w-44">
      {/* Explicit handle ids so the utility edges (heater/cooling/sensors)
          can attach to the top/bottom while the process line uses left/right. */}
      <Handle type="target" id="left" position={Position.Left} className="!bg-cyan-500/80" />
      <Handle type="source" id="right" position={Position.Right} className="!bg-cyan-500/80" />
      <Handle type="target" id="top" position={Position.Top} className="!bg-cyan-500/80" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="!bg-cyan-500/80" />
      <div
        data-sf-state={data.flash ? '' : undefined}
        className={`relative rounded-xl border px-3 py-2 text-left shadow-lg ${CARD_TONE[data.tone]}`}
      >
        {data.pulse && (
          <span
            data-sf-pulse=""
            aria-hidden="true"
            className={`pointer-events-none absolute -inset-px rounded-xl border ${PULSE_TONE[data.tone]}`}
          />
        )}
        <div className="relative flex items-center gap-2">
          <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${DOT_TONE[data.tone]}`} />
          <p className="truncate text-xs font-semibold text-slate-100">{data.title}</p>
          {data.rotor && (
            <span
              data-sf-rotor=""
              aria-hidden="true"
              className="ml-auto h-3 w-3 shrink-0 rounded-full border-2 border-dashed border-emerald-400/80"
            />
          )}
        </div>
        <p className="relative mt-1 text-[10px] tracking-wide text-slate-400 uppercase">{data.subtitle}</p>
        <p className="relative font-mono text-[11px] text-cyan-300">{data.detail}</p>
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

function buildGraph(
  plant: PlantDetail,
  values: ProcessSnapshot,
  safetyStatus: SafetyStatus,
): { nodes: UnitNode[]; edges: Edge[] } {
  const { config, safety_limits: limits } = plant
  const pumpRunning = values.pump_running
  const reactorTone: Tone =
    safetyStatus === 'violation' ? 'crit' : safetyStatus === 'safe' ? 'ok' : safetyStatus === 'unknown' ? 'idle' : 'warn'

  const nodes: UnitNode[] = [
    {
      id: 'feed',
      type: 'unit',
      position: { x: 0, y: 70 },
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
      position: { x: 250, y: 70 },
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
      position: { x: 500, y: 70 },
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
      position: { x: 750, y: 70 },
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
      position: { x: 1000, y: 70 },
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
      position: { x: 330, y: -70 },
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
      position: { x: 600, y: -70 },
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
      position: { x: 600, y: 220 },
      data: {
        title: 'Sensors',
        subtitle: 'T · P · L',
        detail: safetyStatus === 'unknown' ? 'Awaiting telemetry' : safetyStatus.replace('_', ' '),
        tone: safetyStatus === 'violation' ? 'crit' : safetyStatus === 'safe' ? 'ok' : safetyStatus === 'unknown' ? 'idle' : 'warn',
      },
    },
  ]

  const edges: Edge[] = [
    { id: 'e-feed-pump', source: 'feed', target: 'pump', sourceHandle: 'right', targetHandle: 'left', className: 'sf-flow-main' },
    { id: 'e-pump-reactor', source: 'pump', target: 'reactor', sourceHandle: 'right', targetHandle: 'left', className: 'sf-flow-main' },
    { id: 'e-reactor-valve', source: 'reactor', target: 'valve', sourceHandle: 'right', targetHandle: 'left', className: 'sf-flow-main' },
    { id: 'e-valve-product', source: 'valve', target: 'product', sourceHandle: 'right', targetHandle: 'left', className: 'sf-flow-main' },
    { id: 'e-heater-reactor', source: 'heater', target: 'reactor', sourceHandle: 'bottom', targetHandle: 'top', animated: false },
    { id: 'e-cooling-reactor', source: 'cooling', target: 'reactor', sourceHandle: 'bottom', targetHandle: 'top', animated: false },
    { id: 'e-reactor-sensors', source: 'reactor', target: 'sensors', sourceHandle: 'bottom', targetHandle: 'top', animated: false },
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
  const { nodes, edges } = useMemo(() => buildGraph(plant, values, safetyStatus), [plant, values, safetyStatus])

  useProcessMotion(container, {
    reducedMotion,
    hasTelemetry: safetyStatus !== 'unknown',
    pumpRunning: values.pump_running,
    safetyStatus,
    stateKey: safetyStatus,
  })

  return (
    <div
      ref={container}
      className={`overflow-hidden rounded-xl border border-slate-800 bg-slate-950 ${className}`}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
        preventScrolling={false}
      >
        <Background color="#1e293b" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
