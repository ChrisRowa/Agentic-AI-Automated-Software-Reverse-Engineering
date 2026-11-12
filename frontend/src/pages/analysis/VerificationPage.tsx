import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ShieldCheck, ShieldAlert, ShieldX, Shield,
  FileCode, CheckCircle2, AlertCircle, HelpCircle, XCircle,
  RefreshCw, Info, ChevronDown, ChevronUp
} from 'lucide-react'
import { getVerification, getEvidence } from '../../api/client'
import type { Project } from '../../store/appStore'

const STATUS_CONFIG = {
  VERIFIED:    { icon: CheckCircle2,  cls: 'badge-verified',    iconCls: 'text-emerald-400', label: 'Verified',     bg: 'bg-emerald-500/10 border-emerald-500/20' },
  INFERRED:    { icon: Info,          cls: 'badge-inferred',    iconCls: 'text-blue-400',    label: 'Inferred',     bg: 'bg-blue-500/10 border-blue-500/20' },
  UNCERTAIN:   { icon: HelpCircle,    cls: 'badge-uncertain',   iconCls: 'text-amber-400',   label: 'Uncertain',    bg: 'bg-amber-500/10 border-amber-500/20' },
  UNSUPPORTED: { icon: XCircle,       cls: 'badge-unsupported', iconCls: 'text-red-400',     label: 'Unsupported',  bg: 'bg-red-500/10 border-red-500/20' },
}

function ClaimCard({ claim }: { claim: any }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CONFIG[claim.verification_status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.UNCERTAIN
  const Icon = cfg.icon

  return (
    <div className={`card p-4 border ${cfg.bg} transition-all`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <Icon size={16} className={`${cfg.iconCls} flex-shrink-0 mt-0.5`} />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-200 leading-relaxed">{claim.claim_text}</p>
            <div className="flex items-center gap-3 mt-2">
              <span className={cfg.cls}>{cfg.label}</span>
              {claim.claim_type && <span className="tag">{claim.claim_type}</span>}
              {claim.agent_source && <span className="text-xs text-slate-500">by {claim.agent_source}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right">
            <div className="text-sm font-bold text-slate-100">
              {claim.confidence ? `${Math.round(claim.confidence * 100)}%` : '—'}
            </div>
            <div className="text-xs text-slate-500">confidence</div>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="btn-ghost p-1 rounded-lg"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {expanded && claim.evidence_ids?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-surface-700/50">
          <p className="text-xs text-slate-500 mb-2">Evidence IDs:</p>
          <div className="flex flex-wrap gap-1">
            {claim.evidence_ids.map((id: string) => (
              <span key={id} className="tag text-xs font-mono">{id?.slice(0, 8)}…</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function VerificationPage() {
  const project = useOutletContext<Project>()
  const [filter, setFilter] = useState<string>('ALL')

  const { data: summary, isLoading: loadingSum, refetch } = useQuery({
    queryKey: ['verification', project.id],
    queryFn: () => getVerification(project.id),
    enabled: ['COMPLETED', 'PARTIAL'].includes(project.status),
  })

  const { data: evidenceData, isLoading: loadingEv } = useQuery({
    queryKey: ['evidence', project.id, filter],
    queryFn: () => getEvidence(project.id),
    enabled: ['COMPLETED', 'PARTIAL'].includes(project.status),
  })

  const claims: any[] = evidenceData?.claims || []
  const filtered = filter === 'ALL' ? claims : claims.filter((c: any) => c.verification_status === filter)

  if (!['COMPLETED', 'PARTIAL'].includes(project.status)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Shield size={48} className="text-slate-600" />
        <p className="text-slate-400">Verification data will be available after analysis completes.</p>
      </div>
    )
  }

  const total = summary?.total || 0
  const stats = [
    { key: 'VERIFIED',    label: 'Verified',    count: summary?.verified || 0,    icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { key: 'INFERRED',    label: 'Inferred',    count: summary?.inferred || 0,    icon: Info,         color: 'text-blue-400',    bg: 'bg-blue-500/10' },
    { key: 'UNCERTAIN',   label: 'Uncertain',   count: summary?.uncertain || 0,   icon: HelpCircle,   color: 'text-amber-400',   bg: 'bg-amber-500/10' },
    { key: 'UNSUPPORTED', label: 'Unsupported', count: summary?.unsupported || 0, icon: XCircle,      color: 'text-red-400',     bg: 'bg-red-500/10' },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <ShieldCheck size={22} className="text-brand-400" />
            Claim Verification
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Evidence-backed verification of all AI-generated claims — hallucination prevention layer
          </p>
        </div>
        <button onClick={() => refetch()} className="btn-secondary" disabled={loadingSum}>
          <RefreshCw size={14} className={loadingSum ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Evidence Model Legend */}
      <div className="card p-4 border-brand-600/20">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Evidence Status Model</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {stats.map(({ key, label, icon: Icon, color, bg }) => (
            <div key={key} className={`flex items-center gap-2 px-3 py-2 rounded-lg ${bg}`}>
              <Icon size={14} className={color} />
              <div>
                <div className={`text-xs font-semibold ${color}`}>{label}</div>
                <div className="text-xs text-slate-500 leading-tight">
                  {key === 'VERIFIED' ? 'Direct source evidence' :
                   key === 'INFERRED' ? 'Multi-evidence derived' :
                   key === 'UNCERTAIN' ? 'Insufficient evidence' :
                   'No evidence found'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(({ key, label, count, icon: Icon, color, bg }) => (
          <button
            key={key}
            onClick={() => setFilter(filter === key ? 'ALL' : key)}
            className={`stat-card text-left hover:border-brand-600/30 transition-all ${
              filter === key ? 'border-brand-600/50 ring-1 ring-brand-600/20' : ''
            }`}
          >
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${bg}`}>
              <Icon size={16} className={color} />
            </div>
            <div className="stat-value">{count}</div>
            <div className="stat-label">{label}</div>
            {total > 0 && (
              <div className="text-xs text-slate-500 mt-0.5">
                {Math.round((count / total) * 100)}% of {total}
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Confidence visualization */}
      {total > 0 && (
        <div className="card p-5">
          <h3 className="section-title mb-4">Verification Distribution</h3>
          <div className="h-6 rounded-full overflow-hidden flex">
            {stats.map(({ key, count }) => {
              const pct = total > 0 ? (count / total) * 100 : 0
              if (pct === 0) return null
              return (
                <div
                  key={key}
                  style={{ width: `${pct}%` }}
                  className={`h-full transition-all ${
                    key === 'VERIFIED' ? 'bg-emerald-500' :
                    key === 'INFERRED' ? 'bg-blue-500' :
                    key === 'UNCERTAIN' ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  title={`${key}: ${count} (${pct.toFixed(1)}%)`}
                />
              )
            })}
          </div>
          <div className="flex items-center gap-4 mt-2">
            {stats.map(({ key, label, count, color }) => (
              <div key={key} className="flex items-center gap-1 text-xs text-slate-400">
                <div className={`w-2 h-2 rounded-full ${
                  key === 'VERIFIED' ? 'bg-emerald-500' :
                  key === 'INFERRED' ? 'bg-blue-500' :
                  key === 'UNCERTAIN' ? 'bg-amber-500' : 'bg-red-500'
                }`} />
                {label}: {count}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex items-center gap-2">
        {['ALL', 'VERIFIED', 'INFERRED', 'UNCERTAIN', 'UNSUPPORTED'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={filter === f ? 'btn-primary text-xs py-1.5' : 'btn-secondary text-xs py-1.5'}
          >
            {f === 'ALL' ? `All Claims (${total})` : f}
          </button>
        ))}
      </div>

      {/* Claims list */}
      {loadingEv ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <div key={i} className="skeleton h-20 w-full" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-10 flex flex-col items-center gap-4">
          <ShieldCheck size={40} className="text-slate-600" />
          <p className="text-slate-400 text-center">
            {total === 0
              ? 'No claims have been generated yet. Use the Ask AI feature to generate evidence-backed answers.'
              : `No claims with status "${filter}".`}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">{filtered.length} claims</p>
          {filtered.map((claim: any) => (
            <ClaimCard key={claim.id} claim={claim} />
          ))}
        </div>
      )}
    </div>
  )
}
