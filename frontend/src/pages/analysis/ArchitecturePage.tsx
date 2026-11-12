import React from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Network, Loader2, AlertCircle, Info } from 'lucide-react'
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow'
import type { Node, Edge } from 'reactflow'
import 'reactflow/dist/style.css'
import { getGraph } from '../../api/client'
import type { Project } from '../../store/appStore'

const NODE_COLORS: Record<string, string> = {
  FILE: '#3b82f6',
  CLASS: '#8b5cf6',
  FUNCTION: '#10b981',
  METHOD: '#06b6d4',
  MODULE: '#f59e0b',
  REPOSITORY: '#6366f1',
  API: '#ef4444',
  DATABASE: '#f97316',
}

function buildFlowNodes(graphNodes: any[], graphEdges: any[]): [Node[], Edge[]] {
  const nodeMap: Record<string, Node> = {}
  
  // Group by module/file for positioning
  const byType: Record<string, any[]> = {}
  for (const n of graphNodes) {
    const t = n.node_type || 'FILE'
    if (!byType[t]) byType[t] = []
    byType[t].push(n)
  }

  let x = 0
  for (const [type, nodes] of Object.entries(byType)) {
    let y = 0
    for (const n of nodes) {
      nodeMap[n.id] = {
        id: n.id,
        position: { x: x * 220, y: y * 80 },
        data: { 
          label: n.label,
          type: n.node_type,
          file: n.file_path,
          line: n.line_start,
        },
        style: {
          background: NODE_COLORS[type] || '#64748b',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          padding: '6px 12px',
          fontSize: '11px',
          fontFamily: 'JetBrains Mono, monospace',
          boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
          maxWidth: '180px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        },
        type: 'default',
      }
      y++
    }
    x++
  }

  const edges: Edge[] = graphEdges.slice(0, 200).map((e) => ({
    id: e.id || `${e.source_id}-${e.target_id}`,
    source: e.source_id,
    target: e.target_id,
    label: e.relationship_type,
    animated: e.relationship_type === 'CALLS',
    style: { 
      stroke: e.relationship_type === 'CALLS' ? '#6366f1' :
              e.relationship_type === 'IMPORTS' ? '#10b981' :
              e.relationship_type === 'INHERITS' ? '#8b5cf6' : '#64748b',
      strokeWidth: 1.5,
    },
    labelStyle: { fill: '#94a3b8', fontSize: '10px' },
    labelBgStyle: { fill: '#1e293b' },
  }))

  return [Object.values(nodeMap), edges]
}

export default function ArchitecturePage() {
  const project = useOutletContext<Project>()

  const { data, isLoading, error } = useQuery({
    queryKey: ['graph', project.id],
    queryFn: () => getGraph(project.id, { limit: 300 }),
    enabled: ['COMPLETED', 'PARTIAL'].includes(project.status),
  })

  if (!['COMPLETED', 'PARTIAL'].includes(project.status)) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center text-slate-400">
          <Loader2 size={24} className="animate-spin mx-auto mb-2 text-brand-400" />
          Analysis in progress...
        </div>
      </div>
    )
  }

  const [flowNodes, flowEdges] = data 
    ? buildFlowNodes(data.nodes || [], data.edges || [])
    : [[], []]

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Network size={22} className="text-brand-400" />
          Architecture View
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Interactive program knowledge graph. {data?.total_nodes || 0} nodes, {data?.total_edges || 0} edges.
        </p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs text-slate-300">
            <div className="w-3 h-3 rounded" style={{ background: color }} />
            {type}
          </div>
        ))}
      </div>

      {isLoading ? (
        <div className="card h-96 flex items-center justify-center">
          <Loader2 size={24} className="animate-spin text-brand-400" />
        </div>
      ) : error ? (
        <div className="card h-96 flex items-center justify-center">
          <div className="text-center text-slate-400">
            <AlertCircle size={24} className="mx-auto mb-2 text-red-400" />
            Failed to load graph data
          </div>
        </div>
      ) : flowNodes.length === 0 ? (
        <div className="card h-96 flex items-center justify-center">
          <div className="text-center text-slate-400">
            <Info size={24} className="mx-auto mb-2" />
            No graph nodes found
          </div>
        </div>
      ) : (
        <div className="card h-[600px] overflow-hidden">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            fitView
            attributionPosition="bottom-right"
            style={{ background: '#0f172a' }}
          >
            <Background color="#334155" gap={20} size={1} />
            <Controls />
            <MiniMap
              nodeColor={(n) => NODE_COLORS[(n.data as any)?.type] || '#64748b'}
              style={{ background: '#1e293b', border: '1px solid #334155' }}
            />
          </ReactFlow>
        </div>
      )}
    </div>
  )
}
