import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  Zap, Search, Loader2, AlertCircle, ArrowRight,
  FileCode, Activity, Info, GitGraph, Code2, Layers
} from 'lucide-react'
import { impactAnalysis } from '../../api/client'
import type { Project } from '../../store/appStore'

const ENTITY_TYPES = ['function', 'class', 'file', 'module', 'method']

export default function ChangeImpactPage() {
  const project = useOutletContext<Project>()
  const [entity, setEntity] = useState('')
  const [entityType, setEntityType] = useState('function')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = async () => {
    if (!entity.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await impactAnalysis(project.id, entity.trim(), entityType)
      setResult(r)
    } catch (e: any) {
      setError(e.message || 'Impact analysis failed')
    } finally {
      setLoading(false)
    }
  }

  if (!['COMPLETED', 'PARTIAL'].includes(project.status)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Zap size={48} className="text-slate-600" />
        <p className="text-slate-400">Change impact analysis will be available after analysis completes.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Zap size={22} className="text-brand-400" />
          Change Impact Analysis
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Analyze what components are affected if you change a function, class, file, or module
        </p>
      </div>

      {/* Info */}
      <div className="card p-4 border-amber-500/20 bg-amber-500/5">
        <div className="flex items-start gap-3">
          <Info size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-slate-300">
            <span className="font-medium text-amber-300">Reverse Traceability &amp; Change Impact: </span>
            Uses graph traversal on the call graph and dependency graph to identify all code that depends on 
            the changed entity. Results are confidence-rated and ranked by relationship type.
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="card p-5 space-y-4">
        <h3 className="section-title">Analysis Configuration</h3>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Entity Type</label>
          <div className="flex gap-2 flex-wrap">
            {ENTITY_TYPES.map(t => (
              <button
                key={t}
                onClick={() => setEntityType(t)}
                className={entityType === t ? 'btn-primary text-xs py-1.5' : 'btn-secondary text-xs py-1.5'}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Entity Name
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={entity}
              onChange={(e) => setEntity(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              placeholder={`e.g., ${
                entityType === 'function' ? 'authenticate, process_payment' :
                entityType === 'class' ? 'UserService, AuthManager' :
                entityType === 'file' ? 'database.py, auth.py' :
                entityType === 'module' ? 'authentication, payments' :
                'User.save, Auth.validate'
              }`}
              className="input flex-1"
            />
            <button
              onClick={handleAnalyze}
              disabled={loading || !entity.trim()}
              className="btn-primary"
              id="impact-analyze-btn"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              {loading ? 'Analyzing…' : 'Analyze Impact'}
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
          {/* Summary metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="stat-card">
              <div className="w-8 h-8 rounded-lg bg-red-500/15 flex items-center justify-center mb-3">
                <Activity size={16} className="text-red-400" />
              </div>
              <div className="stat-value">{result.affected_callers?.length || 0}</div>
              <div className="stat-label">Callers Affected</div>
            </div>
            <div className="stat-card">
              <div className="w-8 h-8 rounded-lg bg-orange-500/15 flex items-center justify-center mb-3">
                <GitGraph size={16} className="text-orange-400" />
              </div>
              <div className="stat-value">{result.affected_callees?.length || 0}</div>
              <div className="stat-label">Callees</div>
            </div>
            <div className="stat-card">
              <div className="w-8 h-8 rounded-lg bg-brand-500/15 flex items-center justify-center mb-3">
                <FileCode size={16} className="text-brand-400" />
              </div>
              <div className="stat-value">{result.affected_files?.length || 0}</div>
              <div className="stat-label">Files Affected</div>
            </div>
            <div className="stat-card">
              <div className="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center mb-3">
                <Layers size={16} className="text-purple-400" />
              </div>
              <div className="stat-value">{result.affected_classes?.length || 0}</div>
              <div className="stat-label">Classes Affected</div>
            </div>
          </div>

          {/* Explanation */}
          {result.explanation && (
            <div className="card p-5">
              <h3 className="section-title mb-3">Impact Summary</h3>
              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{result.explanation}</p>
            </div>
          )}

          {/* Evidence path */}
          {result.evidence_path?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">
                <Zap size={16} className="text-brand-400" />
                Impact Path
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                {result.evidence_path.map((step: string, i: number) => (
                  <React.Fragment key={i}>
                    <span className="tag font-mono">{step}</span>
                    {i < result.evidence_path.length - 1 && (
                      <ArrowRight size={14} className="text-slate-600 flex-shrink-0" />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Callers */}
          {result.affected_callers?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">
                <Activity size={16} className="text-red-400" />
                Callers (will be affected by this change)
              </h3>
              <div className="space-y-2">
                {result.affected_callers.map((caller: string, i: number) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 bg-red-500/5 border border-red-500/20 rounded-lg">
                    <Code2 size={13} className="text-red-400 flex-shrink-0" />
                    <span className="text-sm font-mono text-slate-300">{caller}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Callees */}
          {result.affected_callees?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">
                <GitGraph size={16} className="text-orange-400" />
                Callees (called by this entity)
              </h3>
              <div className="space-y-2">
                {result.affected_callees.map((callee: string, i: number) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 bg-orange-500/5 border border-orange-500/20 rounded-lg">
                    <Code2 size={13} className="text-orange-400 flex-shrink-0" />
                    <span className="text-sm font-mono text-slate-300">{callee}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Affected files */}
          {result.affected_files?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">
                <FileCode size={16} className="text-brand-400" />
                Affected Files
              </h3>
              <div className="space-y-2">
                {result.affected_files.map((f: string, i: number) => (
                  <div key={i} className="flex items-center gap-2 p-2 bg-surface-900/60 rounded-lg">
                    <FileCode size={13} className="text-slate-500" />
                    <span className="text-sm font-mono text-slate-300">{f}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div className="card p-10 flex flex-col items-center gap-4">
          <Zap size={40} className="text-slate-600" />
          <div className="text-center">
            <p className="text-slate-300 font-medium">Enter an entity name to analyze change impact</p>
            <p className="text-slate-500 text-sm mt-1">
              Discovers all components that depend on the specified entity using graph traversal
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
