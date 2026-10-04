import { memo, useMemo } from 'react'
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
import type { PlantDetail } from '../../types/plant'

/**
 * Static process topology preview for the locked MVP process:
 *   Feed Tank → Pump P-101 → Heated Reactor R-101 → Outlet Valve V-101 → Product Tank
 *
 * This is a *diagram of the configured model* — a preview of what the
 * simulation will exercise in later parts. It never animates and never implies
 * live plant control (SAFEFLUX_MASTER timeline rule).
 */

type Tone = 'ok' | 'warn' | 'idle'

type UnitNodeData = Record<string, unknown> & {
  title: string
  subtitle: string
  detail: string
  tone: Tone
}

type UnitNode = Node<UnitNodeData, 'unit'>

const TONE_CLASS: Record<Tone, string> = {
  ok: 'border-emerald-500/50 bg-emerald-500/5',
  warn: 'border-amber-500/50 bg-amber-500/5',
  idle: 'border-slate-700 bg-slate-900/70',
}

const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-emerald-400',
  warn: 'bg-amber-400',
  idle: 'bg-slate-500',
}

const UnitNodeComponent = memo(function UnitNodeComponent({ data }: NodeProps<UnitNode>) {
  return (
    <div
      className={`w-44 rounded-xl border px-3 py-2 text-left shadow-lg ${TONE_CLASS[data.tone]}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-cyan-500" />
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${TONE_DOT[data.tone]}`} />
        <p className="text-xs font-semibold text-slate-100">{data.title}</p>
      </div>
      <p className="mt-1 text-[10px] tracking-wide text-slate-400 uppercase">{data.subtitle}</p>
      <p className="mt-1 font-mono text-[11px] text-cyan-300">{data.detail}</p>
      <Handle type="source" position={Position.Right} className="!bg-cyan-500" />
    </div>
  )
})

const nodeTypes = { unit: UnitNodeComponent }

function tone(pumpRunning: boolean, value: number, limit: number): Tone {
  if (!pumpRunning) return 'idle'
  return value >= limit * 0.9 ? 'warn' : 'ok'
}

function buildGraph(plant: PlantDetail): { nodes: UnitNode[]; edges: Edge[] } {
  const { state, safety_limits: limits } = plant
  const pumpTone: Tone = state.pump_running ? 'ok' : 'idle'

  const nodes: UnitNode[] = [
    {
      id: 'feed',
      type: 'unit',
      position: { x: 0, y: 40 },
      data: {
        title: 'Feed Tank',
        subtitle: 'Raw feed',
        detail: `Level ${state.level_pct.toFixed(1)}%`,
        tone: tone(state.pump_running, state.level_pct, limits.max_level_pct),
      },
    },
    {
      id: 'pump',
      type: 'unit',
      position: { x: 240, y: 40 },
      data: {
        title: 'Pump P-101',
        subtitle: 'Feed pump',
        detail: state.pump_running ? 'Running' : 'Stopped',
        tone: pumpTone,
      },
    },
    {
      id: 'reactor',
      type: 'unit',
      position: { x: 480, y: 40 },
      data: {
        title: 'Heated Reactor R-101',
        subtitle: 'Heater · Cooling · Sensors',
        detail: `${state.temperature_c.toFixed(0)}°C · ${state.pressure_bar.toFixed(1)} bar`,
        tone: tone(state.pump_running, state.temperature_c, limits.max_temperature_c),
      },
    },
    {
      id: 'valve',
      type: 'unit',
      position: { x: 720, y: 40 },
      data: {
        title: 'Outlet Valve V-101',
        subtitle: 'Discharge control',
        detail: `${plant.config.valve_position_pct.toFixed(0)}% open`,
        tone: state.pump_running ? 'ok' : 'idle',
      },
    },
    {
      id: 'product',
      type: 'unit',
      position: { x: 960, y: 40 },
      data: {
        title: 'Product Tank',
        subtitle: 'Discharge',
        detail: `Feed ${plant.config.feed_flow_lpm.toFixed(0)} L/min`,
        tone: state.pump_running ? 'ok' : 'idle',
      },
    },
  ]

  const edges: Edge[] = [
    { id: 'e-feed-pump', source: 'feed', target: 'pump', animated: false },
    { id: 'e-pump-reactor', source: 'pump', target: 'reactor', animated: false },
    { id: 'e-reactor-valve', source: 'reactor', target: 'valve', animated: false },
    { id: 'e-valve-product', source: 'valve', target: 'product', animated: false },
  ]

  return { nodes, edges }
}

export function ProcessTopology({ plant }: { plant: PlantDetail }) {
  const { nodes, edges } = useMemo(() => buildGraph(plant), [plant])

  return (
    <div className="h-52 w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950 sm:h-64">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
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
