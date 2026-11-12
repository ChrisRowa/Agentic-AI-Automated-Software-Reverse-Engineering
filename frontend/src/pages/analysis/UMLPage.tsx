import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  SquareDashedBottom, Download, Loader2, RefreshCw,
  Code2, GitGraph, Layers, AlertCircle, CheckCircle2, Copy
} from 'lucide-react'
import { generateUML } from '../../api/client'
import type { Project } from '../../store/appStore'

const DIAGRAM_TYPES = [
  { id: 'class',    label: 'Class Diagram',    icon: Layers,    desc: 'Classes, attributes, methods, inheritance' },
  { id: 'sequence', label: 'Sequence Diagram',  icon: GitGraph,  desc: 'Call flow between components' },
  { id: 'dependency', label: 'Dependency Graph', icon: Code2,   desc: 'Module/file import relationships' },
  { id: 'architecture', label: 'Architecture',  icon: SquareDashedBottom, desc: 'High-level system view' },
]

function MermaidViewer({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500 font-mono">Mermaid / PlantUML notation</span>
        <div className="flex gap-2">
          <button onClick={handleCopy} className="btn-secondary text-xs py-1">
            {copied ? <CheckCircle2 size={12} className="text-emerald-400" /> : <Copy size={12} />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={() => {
              const blob = new Blob([code], { type: 'text/plain' })
              const a = document.createElement('a')
              a.href = URL.createObjectURL(blob)
              a.download = 'diagram.mmd'
              a.click()
            }}
            className="btn-secondary text-xs py-1"
          >
            <Download size={12} />
            Download
          </button>
        </div>
      </div>
      <div className="code-block max-h-[500px] overflow-auto relative">
        <pre className="text-xs leading-relaxed whitespace-pre-wrap">{code}</pre>
      </div>
    </div>
  )
}

export default function UMLPage() {
  const project = useOutletContext<Project>()
  const [selectedType, setSelectedType] = useState('class')
  const [scope, setScope] = useState('')
  const [result, setResult] = useState<any>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    setResult(null)
    try {
      const r = await generateUML(project.id, selectedType, scope || undefined)
      setResult(r)
    } catch (e: any) {
      setError(e.message || 'Failed to generate UML')
    } finally {
      setGenerating(false)
    }
  }

  if (!['COMPLETED', 'PARTIAL'].includes(project.status)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <SquareDashedBottom size={48} className="text-slate-600" />
        <p className="text-slate-400">UML generation will be available after analysis completes.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <SquareDashedBottom size={22} className="text-brand-400" />
          UML Diagrams
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Code-grounded UML generation — derived from actual AST and call graph, not LLM guessing
        </p>
      </div>

      {/* Note about code-grounded UML */}
      <div className="card p-4 border-brand-600/20 flex items-start gap-3">
        <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-slate-300 font-medium">Code-Grounded UML Reconstruction</p>
          <p className="text-xs text-slate-400 mt-0.5">
            All diagrams are derived directly from the program knowledge graph, call graphs, and AST analysis.
            No LLM hallucination — every relationship has a source evidence reference.
          </p>
        </div>
      </div>

      {/* Diagram type selection */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {DIAGRAM_TYPES.map(({ id, label, icon: Icon, desc }) => (
          <button
            key={id}
            onClick={() => setSelectedType(id)}
            className={`card p-4 text-left transition-all ${
              selectedType === id
                ? 'border-brand-600/60 bg-brand-600/10 ring-1 ring-brand-600/20'
                : 'hover:border-surface-600'
            }`}
          >
            <Icon size={20} className={selectedType === id ? 'text-brand-400' : 'text-slate-500'} />
            <div className="mt-2 text-sm font-medium text-slate-200">{label}</div>
            <div className="text-xs text-slate-500 mt-0.5">{desc}</div>
          </button>
        ))}
      </div>

      {/* Scope filter */}
      <div className="card p-4">
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Scope Filter <span className="text-slate-500 font-normal">(optional — e.g., module name, class name)</span>
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder="e.g., auth, UserService, api.py — leave empty for full project"
            className="input flex-1"
          />
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="btn-primary"
            id="generate-uml-btn"
          >
            {generating ? <Loader2 size={16} className="animate-spin" /> : <SquareDashedBottom size={16} />}
            {generating ? 'Generating…' : 'Generate Diagram'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card p-4 border-red-500/30 bg-red-500/5 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="section-title">
                {DIAGRAM_TYPES.find(d => d.id === result.diagram_type)?.label || result.diagram_type}
              </h3>
              <div className="flex items-center gap-3">
                {result.is_verified && (
                  <span className="badge-verified flex items-center gap-1">
                    <CheckCircle2 size={10} /> Verified
                  </span>
                )}
                <span className="tag">{result.format || 'mermaid'}</span>
                {result.node_count != null && (
                  <span className="text-xs text-slate-400">{result.node_count} nodes</span>
                )}
              </div>
            </div>

            {result.content && <MermaidViewer code={result.content} />}

            {result.summary && (
              <div className="mt-4 p-3 bg-surface-900/60 rounded-lg">
                <p className="text-sm text-slate-300">{result.summary}</p>
              </div>
            )}
          </div>

          {/* Evidence */}
          {result.evidence_count != null && (
            <div className="card p-4 flex items-center gap-3">
              <CheckCircle2 size={16} className="text-emerald-400" />
              <p className="text-sm text-slate-300">
                Diagram derived from{' '}
                <span className="font-semibold text-slate-100">{result.evidence_count}</span>{' '}
                source evidence items (AST nodes, call edges, import relationships).
              </p>
            </div>
          )}
        </div>
      )}

      {/* Instructions when no result */}
      {!result && !generating && !error && (
        <div className="card p-10 flex flex-col items-center gap-4">
          <SquareDashedBottom size={40} className="text-slate-600" />
          <div className="text-center">
            <p className="text-slate-300 font-medium">Select a diagram type and click Generate</p>
            <p className="text-slate-500 text-sm mt-1">
              Diagrams are generated from your analyzed repository structure — not invented by AI
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
