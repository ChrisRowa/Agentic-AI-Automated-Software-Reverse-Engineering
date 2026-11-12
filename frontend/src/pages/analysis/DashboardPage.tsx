import React from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { 
  Code2, Layers, GitGraph, Network, Database, 
  AlertCircle, Loader2, BarChart3, FileCode, 
  CheckCircle2, Clock, Zap, GitBranch
} from 'lucide-react'
import { getOverview, getVerification } from '../../api/client'
import type { Project } from '../../store/appStore'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis } from 'recharts'

const LANG_COLORS: Record<string, string> = {
  Python: '#3b82f6', JavaScript: '#f59e0b', TypeScript: '#6366f1',
  Java: '#f97316', 'C#': '#8b5cf6', Go: '#06b6d4',
  Rust: '#ef4444', HTML: '#ec4899', CSS: '#10b981', default: '#64748b',
}

function StatCard({ icon, label, value, sub, color = 'brand' }: {
  icon: React.ReactNode; label: string; value: string | number; sub?: string; color?: string
}) {
  return (
    <div className="stat-card group hover:border-brand-600/30 transition-colors">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3
        ${color === 'green' ? 'bg-emerald-500/15 text-emerald-400' :
          color === 'blue' ? 'bg-blue-500/15 text-blue-400' :
          color === 'orange' ? 'bg-orange-500/15 text-orange-400' :
          color === 'purple' ? 'bg-purple-500/15 text-purple-400' :
          'bg-brand-500/15 text-brand-400'}`}>
        {icon}
      </div>
      <div className="stat-value">{typeof value === 'number' ? value.toLocaleString() : value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function AnalysisRunning({ project }: { project: Project }) {
  const steps = [
    'EXTRACTING', 'DISCOVERING', 'PARSING', 'BUILDING_GRAPHS',
    'INDEXING', 'AGENT_ANALYSIS', 'VERIFYING'
  ]
  const currentIdx = steps.indexOf(project.status)

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
      <div className="relative">
        <div className="w-24 h-24 rounded-full bg-brand-600/10 border-2 border-brand-600/30 
                        flex items-center justify-center">
          <Loader2 size={36} className="text-brand-400 animate-spin" />
        </div>
        <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-brand-600 
                        flex items-center justify-center text-white text-xs font-bold">
          {project.analysis_progress.toFixed(0)}
        </div>
      </div>

      <div className="text-center max-w-md">
        <h2 className="text-xl font-bold text-slate-100 mb-2">Analysis in Progress</h2>
        <p className="text-slate-400 text-sm">
          The AI pipeline is analyzing your repository. 
          This page will automatically update when complete.
        </p>
      </div>

      {/* Step indicator */}
      <div className="w-full max-w-lg">
        {steps.map((step, i) => (
          <div key={step} className="flex items-center gap-3 mb-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs
              ${i < currentIdx ? 'bg-emerald-500 text-white' :
                i === currentIdx ? 'bg-brand-600 text-white' :
                'bg-surface-700 text-slate-500'}`}>
              {i < currentIdx ? <CheckCircle2 size={12} /> :
               i === currentIdx ? <Loader2 size={12} className="animate-spin" /> :
               i + 1}
            </div>
            <span className={`text-sm ${
              i < currentIdx ? 'text-emerald-400' :
              i === currentIdx ? 'text-brand-300 font-medium' :
              'text-slate-500'
            }`}>
              {step.replace(/_/g, ' ')}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const project = useOutletContext<Project>()
  const isRunning = !['COMPLETED', 'FAILED', 'PARTIAL'].includes(project.status)

  const { data: overview } = useQuery({
    queryKey: ['overview', project.id],
    queryFn: () => getOverview(project.id),
    enabled: !isRunning,
  })

  const { data: verification } = useQuery({
    queryKey: ['verification', project.id],
    queryFn: () => getVerification(project.id),
    enabled: !isRunning,
  })

  if (project.status === 'FAILED') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <AlertCircle size={48} className="text-red-400" />
        <h2 className="text-xl font-semibold text-slate-200">Analysis Failed</h2>
        <p className="text-slate-400 max-w-md text-center">{project.error_message || 'An unexpected error occurred during analysis.'}</p>
      </div>
    )
  }

  if (isRunning) {
    return <AnalysisRunning project={project} />
  }

  const langData = Object.entries(project.detected_languages || {}).map(([name, pct]) => ({
    name, value: pct as number, color: LANG_COLORS[name] || LANG_COLORS.default
  }))

  const verSummary = verification || {}

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">{project.name}</h1>
        <div className="flex items-center gap-3 mt-1">
          <span className="badge-completed"><CheckCircle2 size={10}/>Analysis Complete</span>
          {project.project_type && <span className="tag">{project.project_type}</span>}
          {project.primary_language && <span className="tag">{project.primary_language}</span>}
        </div>
      </div>

      {/* Executive summary */}
      {overview?.executive_summary && (
        <div className="card p-5 border-brand-600/20">
          <h3 className="section-title mb-2"><Zap size={16} className="text-brand-400"/>Executive Summary</h3>
          <p className="text-slate-300 text-sm leading-relaxed">{overview.executive_summary}</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard icon={<FileCode size={16}/>} label="Files" value={project.total_files} color="blue"/>
        <StatCard icon={<Layers size={16}/>} label="Classes" value={project.total_classes} color="purple"/>
        <StatCard icon={<Code2 size={16}/>} label="Functions" value={project.total_functions} color="brand"/>
        <StatCard icon={<GitGraph size={16}/>} label="Dependencies" value={project.total_dependencies} color="orange"/>
        <StatCard icon={<Network size={16}/>} label="APIs" value={project.total_api_endpoints} color="green"/>
        <StatCard icon={<BarChart3 size={16}/>} label="Lines" value={project.total_lines_of_code} color="blue"/>
      </div>

      {/* Charts row */}
      <div className="grid md:grid-cols-2 gap-5">
        {/* Language distribution */}
        {langData.length > 0 && (
          <div className="card p-5">
            <h3 className="section-title mb-4">Language Distribution</h3>
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={120} height={120}>
                <PieChart>
                  <Pie data={langData} cx={60} cy={60} innerRadius={35} outerRadius={55}
                       dataKey="value" paddingAngle={2}>
                    {langData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [`${v}%`, 'Share']} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {langData.map((lang) => (
                  <div key={lang.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: lang.color }} />
                      <span className="text-sm text-slate-300">{lang.name}</span>
                    </div>
                    <span className="text-sm font-medium text-slate-200">{lang.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Verification summary */}
        <div className="card p-5">
          <h3 className="section-title mb-4"><CheckCircle2 size={16} className="text-emerald-400"/>Claim Verification</h3>
          {(verSummary.total || 0) === 0 ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm py-4">
              <Clock size={14}/>
              No claims generated yet
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { key: 'verified',    label: 'Verified',    cls: 'badge-verified',    pct: verSummary.verified || 0 },
                { key: 'inferred',    label: 'Inferred',    cls: 'badge-inferred',    pct: verSummary.inferred || 0 },
                { key: 'uncertain',   label: 'Uncertain',   cls: 'badge-uncertain',   pct: verSummary.uncertain || 0 },
                { key: 'unsupported', label: 'Unsupported', cls: 'badge-unsupported', pct: verSummary.unsupported || 0 },
              ].map((s) => (
                <div key={s.key}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className={s.cls}>{s.label}</span>
                    <span className="text-slate-400">{s.pct}</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" 
                         style={{ width: `${verSummary.total ? (s.pct / verSummary.total) * 100 : 0}%` }} />
                  </div>
                </div>
              ))}
              <p className="text-xs text-slate-500 pt-1">Total: {verSummary.total} claims</p>
            </div>
          )}
        </div>
      </div>

      {/* Frameworks */}
      {(project.detected_frameworks || []).length > 0 && (
        <div className="card p-5">
          <h3 className="section-title mb-3">Detected Frameworks & Technologies</h3>
          <div className="flex flex-wrap gap-2">
            {project.detected_frameworks!.map((fw) => (
              <span key={fw} className="tag px-3 py-1">{fw}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
