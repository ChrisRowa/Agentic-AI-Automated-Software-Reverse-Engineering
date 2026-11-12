import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { GitGraph, Loader2 } from 'lucide-react'
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow'
import type { Node, Edge } from 'reactflow'
import 'reactflow/dist/style.css'
import { getCallGraph } from '../../api/client'
import type { Project } from '../../store/appStore'

export default function CallGraphPage() {
  const project = useOutletContext<Project>()

  const { data, isLoading } = useQuery({
    queryKey: ['callgraph', project.id],
    queryFn: () => getCallGraph(project.id),
    enabled: ['COMPLETED', 'PARTIAL'].includes(project.status),
  })

  const nodes: Node[] = (data?.nodes || []).map((n: any, i: number) => {
    const nodeLabel = n.label || n.name || n.qualified_name || n.symbol_name || `fn_${i}`
    const nodeId = String(n.id || n.node_id || i)
    return {
      id: nodeId,
      position: { x: (i % 5) * 220 + 30, y: Math.floor(i / 5) * 110 + 30 },
      data: {
        label: nodeLabel,
        file: n.file_path || n.file,
        line: n.line_start || n.line,
      },
      style: {
        background: n.node_type === 'METHOD' ? '#0891b2' : '#059669',
        color: '#ffffff',
        border: '1px solid rgba(255,255,255,0.2)',
        borderRadius: '8px',
        padding: '6px 12px',
        fontSize: '12px',
        fontWeight: 600,
        fontFamily: 'JetBrains Mono, monospace',
      },
    }
  })

  const edges: Edge[] = (data?.edges || []).map((e: any, i: number) => {
    const src = String(e.source_id || e.source || '')
    const tgt = String(e.target_id || e.target || '')
    return {
      id: String(e.id || `${src}-${tgt}-${i}`),
      source: src,
      target: tgt,
      label: e.relationship_type || e.label || 'CALLS',
      animated: true,
      style: { stroke: '#6366f1', strokeWidth: 1.8 },
      labelStyle: { fill: '#94a3b8', fontSize: 10, fontWeight: 500 },
    }
  })

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <GitGraph size={22} className="text-brand-400" />
          Call Graph
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          {data?.total_nodes || 0} functions, {data?.total_edges || 0} call relationships
        </p>
      </div>

      <div className="card h-[600px] overflow-hidden">
        {isLoading ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 size={24} className="animate-spin text-brand-400" />
          </div>
        ) : (
          <ReactFlow nodes={nodes} edges={edges} fitView style={{ background: '#0f172a' }}>
            <Background color="#334155" gap={20} />
            <Controls />
            <MiniMap style={{ background: '#1e293b' }} />
          </ReactFlow>
        )}
      </div>
    </div>
  )
}
