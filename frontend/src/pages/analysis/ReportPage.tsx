import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  FileText, Download, Loader2, RefreshCw, AlertCircle,
  CheckCircle2, BarChart3, Code2, Layers, GitGraph,
  ShieldCheck, Clock, Copy
} from 'lucide-react'
import { getReport } from '../../api/client'
import type { Project } from '../../store/appStore'

function SectionCard({ title, icon: Icon, children, className = '' }: {
  title: string; icon: any; children: React.ReactNode; className?: string
}) {
  return (
    <div className={`card p-5 ${className}`}>
      <h3 className="section-title mb-4">
        <Icon size={16} className="text-brand-400" />
        {title}
      </h3>
      {children}
    </div>
  )
}

export default function ReportPage() {
  const project = useOutletContext<Project>()
  const [format, setFormat] = useState<'json' | 'markdown'>('json')
  const [copied, setCopied] = useState(false)

  const { data: report, isLoading, error, refetch } = useQuery({
    queryKey: ['report', project.id, format],
    queryFn: () => getReport(project.id, format),
    enabled: ['COMPLETED', 'PARTIAL'].includes(project.status),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  const handleCopy = () => {
    const content = typeof report === 'string' ? report : JSON.stringify(report, null, 2)
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const content = typeof report === 'string' ? report : JSON.stringify(report, null, 2)
    const ext = format === 'markdown' ? 'md' : 'json'
    const blob = new Blob([content], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${project.name.replace(/\s+/g, '_')}_reconstruction_report.${ext}`
    a.click()
  }

  if (!['COMPLETED', 'PARTIAL'].includes(project.status)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <FileText size={48} className="text-slate-600" />
        <p className="text-slate-400">The System Reconstruction Report will be available after analysis completes.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <FileText size={22} className="text-brand-400" />
            System Reconstruction Report
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Complete evidence-backed analysis of the {project.name} repository
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            {(['json', 'markdown'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={format === f ? 'btn-primary text-xs py-1.5' : 'btn-secondary text-xs py-1.5'}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
          <button onClick={handleCopy} className="btn-secondary" disabled={!report}>
            {copied ? <CheckCircle2 size={14} className="text-emerald-400" /> : <Copy size={14} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button onClick={handleDownload} className="btn-primary" disabled={!report}>
            <Download size={14} />
            Download
          </button>
          <button onClick={() => refetch()} className="btn-secondary">
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Summary stats from project */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center mb-3">
            <Code2 size={16} className="text-blue-400" />
          </div>
          <div className="stat-value">{project.total_files}</div>
          <div className="stat-label">Total Files</div>
        </div>
        <div className="stat-card">
          <div className="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center mb-3">
            <Layers size={16} className="text-purple-400" />
          </div>
          <div className="stat-value">{project.total_classes}</div>
          <div className="stat-label">Classes</div>
        </div>
        <div className="stat-card">
          <div className="w-8 h-8 rounded-lg bg-brand-500/15 flex items-center justify-center mb-3">
            <Code2 size={16} className="text-brand-400" />
          </div>
          <div className="stat-value">{project.total_functions}</div>
          <div className="stat-label">Functions</div>
        </div>
        <div className="stat-card">
          <div className="w-8 h-8 rounded-lg bg-orange-500/15 flex items-center justify-center mb-3">
            <GitGraph size={16} className="text-orange-400" />
          </div>
          <div className="stat-value">{project.total_dependencies}</div>
          <div className="stat-label">Dependencies</div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card p-4 border-red-500/30 bg-red-500/5 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300">{(error as Error).message}</p>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="card p-10 flex flex-col items-center gap-4">
          <Loader2 size={36} className="text-brand-400 animate-spin" />
          <p className="text-slate-400">Generating System Reconstruction Report…</p>
        </div>
      )}

      {/* Report content — JSON format renders structured view */}
      {report && format === 'json' && typeof report === 'object' && (
        <div className="space-y-4">
          {/* Executive Summary */}
          {report.executive_summary && (
            <SectionCard title="Executive Summary" icon={FileText}>
              <p className="text-slate-300 text-sm leading-relaxed">{report.executive_summary}</p>
            </SectionCard>
          )}

          {/* Architecture */}
          {report.architecture_summary && (
            <SectionCard title="Architecture Summary" icon={Layers}>
              <p className="text-slate-300 text-sm leading-relaxed">{report.architecture_summary}</p>
              {report.architectural_layers && (
                <div className="mt-4 space-y-2">
                  {report.architectural_layers.map((layer: string, i: number) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-surface-900/60 rounded-lg">
                      <div className="w-2 h-2 rounded-full bg-brand-400" />
                      <span className="text-sm text-slate-300">{layer}</span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          )}

          {/* Key modules */}
          {report.key_modules?.length > 0 && (
            <SectionCard title="Key Modules" icon={BarChart3}>
              <div className="space-y-3">
                {report.key_modules.map((mod: any, i: number) => (
                  <div key={i} className="p-3 bg-surface-900/60 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-slate-200 font-mono">{mod.name}</span>
                      {mod.language && <span className="tag text-xs">{mod.language}</span>}
                    </div>
                    {mod.summary && <p className="text-xs text-slate-400">{mod.summary}</p>}
                    {mod.file_count != null && (
                      <p className="text-xs text-slate-500 mt-1">{mod.file_count} files</p>
                    )}
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Verification summary */}
          {report.verification_summary && (
            <SectionCard title="Claim Verification Summary" icon={ShieldCheck}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {['verified', 'inferred', 'uncertain', 'unsupported'].map(key => (
                  <div key={key} className="text-center p-3 bg-surface-900/60 rounded-lg">
                    <div className="text-xl font-bold text-slate-100">
                      {report.verification_summary[key] || 0}
                    </div>
                    <div className="text-xs text-slate-400 capitalize">{key}</div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Metadata */}
          <SectionCard title="Report Metadata" icon={Clock}>
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Generated', report.generated_at ? new Date(report.generated_at).toLocaleString() : 'Just now'],
                ['Project ID', project.id.slice(0, 8) + '…'],
                ['Primary Language', project.primary_language || '—'],
                ['Analysis Status', project.status],
                ['Lines of Code', (project.total_lines_of_code || 0).toLocaleString()],
                ['Frameworks', (project.detected_frameworks || []).join(', ') || '—'],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center gap-3 p-2 bg-surface-900/60 rounded-lg">
                  <span className="text-xs text-slate-500 w-28 flex-shrink-0">{label}</span>
                  <span className="text-sm text-slate-300 font-mono truncate">{value}</span>
                </div>
              ))}
            </div>
          </SectionCard>

          {/* Raw JSON toggle */}
          <details className="card">
            <summary className="p-4 cursor-pointer text-sm text-slate-400 hover:text-slate-200 transition-colors">
              View Raw JSON Report
            </summary>
            <div className="code-block rounded-t-none border-t border-surface-700/50 max-h-96 overflow-auto">
              <pre className="text-xs">{JSON.stringify(report, null, 2)}</pre>
            </div>
          </details>
        </div>
      )}

      {/* Markdown view */}
      {report && format === 'markdown' && (
        <div className="card p-5">
          <div className="code-block max-h-[600px] overflow-auto">
            <pre className="text-xs leading-relaxed whitespace-pre-wrap">
              {typeof report === 'string' ? report : JSON.stringify(report, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
