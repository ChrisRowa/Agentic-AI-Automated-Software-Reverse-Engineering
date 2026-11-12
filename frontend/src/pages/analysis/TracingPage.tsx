import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  GitBranch, Search, Loader2, AlertCircle, CheckCircle2,
  ArrowRight, FileCode, ChevronRight, Info
} from 'lucide-react'
import { createTrace } from '../../api/client'
import type { Project } from '../../store/appStore'

const TRACE_DIRECTIONS = [
  { id: 'forward',  label: 'Forward',  desc: 'Code → Dependencies' },
  { id: 'backward', label: 'Backward', desc: 'Callers → Code' },
  { id: 'both',     label: 'Both',     desc: 'Bidirectional' },
]

const SOURCE_TYPES = ['code', 'requirement', 'feature', 'behavior']

function TraceLinkCard({ link, index }: { link: any; index: number }) {
  return (
    <div className="card p-4 hover:border-brand-600/30 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="tag text-xs">{link.relationship || link.link_type}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              link.verification_status === 'VERIFIED' ? 'bg-emerald-500/20 text-emerald-400' :
              link.verification_status === 'INFERRED' ? 'bg-blue-500/20 text-blue-400' :
              'bg-amber-500/20 text-amber-400'
            }`}>{link.verification_status || 'INFERRED'}</span>
          </div>
          
          {/* Link visualization */}
          <div className="flex items-center gap-2 flex-wrap mt-2">
            <div className="bg-surface-900/80 rounded-lg px-3 py-1.5">
              <span className="text-xs text-slate-500 mr-1">{link.source_type || 'code'}</span>
              <span className="text-sm font-medium text-slate-200 font-mono">{link.source}</span>
            </div>
            <ArrowRight size={14} className="text-slate-600 flex-shrink-0" />
            <div className="bg-surface-900/80 rounded-lg px-3 py-1.5">
              <span className="text-xs text-slate-500 mr-1">{link.target_type || 'code'}</span>
              <span className="text-sm font-medium text-slate-200 font-mono">{link.target}</span>
            </div>
          </div>

          {/* File reference */}
          {link.file && (
            <div className="flex items-center gap-1 mt-2">
              <FileCode size={12} className="text-slate-500" />
              <span className="text-xs text-slate-400 font-mono">{link.file}</span>
              {link.line_start && <span className="text-xs text-slate-500">:{link.line_start}</span>}
            </div>
          )}
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-sm font-bold text-slate-100">
            {link.confidence ? `${Math.round(link.confidence * 100)}%` : '—'}
          </div>
          <div className="text-xs text-slate-500">confidence</div>
        </div>
      </div>
    </div>
  )
}

export default function TracingPage() {
  const project = useOutletContext<Project>()
  const [source, setSource] = useState('')
  const [sourceType, setSourceType] = useState('code')
  const [direction, setDirection] = useState('forward')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleTrace = async () => {
    if (!source.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await createTrace(project.id, source.trim(), sourceType, direction)
      setResult(r)
    } catch (e: any) {
      setError(e.message || 'Traceability analysis failed')
    } finally {
      setLoading(false)
    }
  }

  if (!['COMPLETED', 'PARTIAL'].includes(project.status)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <GitBranch size={48} className="text-slate-600" />
        <p className="text-slate-400">Traceability analysis will be available after analysis completes.</p>
      </div>
    )
  }

  const links: any[] = result?.links || []
  const path: string[] = result?.path || []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <GitBranch size={22} className="text-brand-400" />
          Requirement Traceability
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Path-aware traceability — links requirements, code, behavior and tests with verified dependency paths
        </p>
      </div>

      {/* Info card */}
      <div className="card p-4 border-blue-500/20 bg-blue-500/5">
        <div className="flex items-start gap-3">
          <Info size={16} className="text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-slate-300">
            <span className="font-medium text-blue-300">Path-Aware Traceability: </span>
            Combines call/dependency graphs to verify the complete
            implementation path. All links derived from static analysis evidence.
          </div>
        </div>
      </div>

      {/* Query form */}
      <div className="card p-5 space-y-4">
        <h3 className="section-title">Trace Configuration</h3>
        
        {/* Source type */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Source Type</label>
          <div className="flex gap-2 flex-wrap">
            {SOURCE_TYPES.map(t => (
              <button
                key={t}
                onClick={() => setSourceType(t)}
                className={sourceType === t ? 'btn-primary text-xs py-1.5' : 'btn-secondary text-xs py-1.5'}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Direction */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Trace Direction</label>
          <div className="grid grid-cols-3 gap-2">
            {TRACE_DIRECTIONS.map(({ id, label, desc }) => (
              <button
                key={id}
                onClick={() => setDirection(id)}
                className={`card p-3 text-left transition-all ${
                  direction === id ? 'border-brand-600/60 bg-brand-600/10' : 'hover:border-surface-600'
                }`}
              >
                <div className="text-sm font-medium text-slate-200">{label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Source identifier */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Source Identifier
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleTrace()}
              placeholder="e.g., login, authenticate, UserService"
              className="input flex-1"
            />
            <button
              onClick={handleTrace}
              disabled={loading || !source.trim()}
              className="btn-primary"
              id="trace-analyze-btn"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              {loading ? 'Tracing…' : 'Trace'}
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card p-4 border-red-500/30 bg-red-500/5 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="card p-5">
            <h3 className="section-title mb-3">Trace Result</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-slate-100">{links.length}</div>
                <div className="text-xs text-slate-400">Trace Links</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-slate-100">
                  {result.confidence ? `${Math.round(result.confidence * 100)}%` : '—'}
                </div>
                <div className="text-xs text-slate-400">Confidence</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-slate-100">{path.length}</div>
                <div className="text-xs text-slate-400">Path Steps</div>
              </div>
            </div>

            {result.explanation && (
              <div className="p-3 bg-surface-900/60 rounded-lg">
                <p className="text-sm text-slate-300">{result.explanation}</p>
              </div>
            )}
          </div>

          {/* Dependency path */}
          {path.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">
                <GitBranch size={16} className="text-brand-400" />
                Trace Path
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                {path.map((step: string, i: number) => (
                  <React.Fragment key={i}>
                    <span className="tag font-mono">{step}</span>
                    {i < path.length - 1 && (
                      <ArrowRight size={12} className="text-slate-600 flex-shrink-0" />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Trace links list */}
          {links.length > 0 && (
            <div className="space-y-3">
              <h3 className="section-title">
                <CheckCircle2 size={16} className="text-brand-400" />
                Trace Links ({links.length})
              </h3>
              {links.map((link: any, i: number) => (
                <TraceLinkCard key={i} link={link} index={i} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div className="card p-10 flex flex-col items-center gap-4">
          <GitBranch size={40} className="text-slate-600" />
          <div className="text-center">
            <p className="text-slate-300 font-medium">Enter a source identifier to begin tracing</p>
            <p className="text-slate-500 text-sm mt-1">
              Supports function names, class names, requirements, and feature names
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
