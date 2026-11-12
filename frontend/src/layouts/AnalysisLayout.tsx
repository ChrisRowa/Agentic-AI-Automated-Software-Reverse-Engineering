import React, { useEffect } from 'react'
import { Outlet, useParams, useNavigate, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Brain, LayoutDashboard, GitGraph, Code2, Network, Scissors,
  GitBranch, SquareDashedBottom, ShieldCheck, MessageSquare,
  FileText, Zap, ChevronLeft, AlertCircle, Loader2, Settings
} from 'lucide-react'
import { getProject } from '../api/client'
import type { Project } from '../store/appStore'

const NAV_ITEMS = [
  { path: 'dashboard',    icon: <LayoutDashboard size={16}/>, label: 'Dashboard' },
  { path: 'architecture', icon: <Network size={16}/>,         label: 'Architecture' },
  { path: 'code',         icon: <Code2 size={16}/>,           label: 'Code Explorer' },
  { path: 'call-graph',   icon: <GitGraph size={16}/>,        label: 'Call Graph' },
  { path: 'slicing',      icon: <Scissors size={16}/>,        label: 'Program Slicing' },
  { path: 'tracing',      icon: <GitBranch size={16}/>,       label: 'Traceability' },
  { path: 'impact',       icon: <Zap size={16}/>,             label: 'Change Impact' },
  { path: 'uml',          icon: <SquareDashedBottom size={16}/>, label: 'UML Diagrams' },
  { path: 'verification', icon: <ShieldCheck size={16}/>,     label: 'Verification' },
  { path: 'ask',          icon: <MessageSquare size={16}/>,   label: 'Ask AI' },
  { path: 'report',       icon: <FileText size={16}/>,        label: 'Report' },
]

function ProgressBar({ progress, status }: { progress: number; status: string }) {
  const isRunning = !['COMPLETED', 'FAILED', 'PARTIAL', 'QUEUED'].includes(status)
  if (!isRunning) return null
  return (
    <div className="px-4 py-2 border-b border-surface-700/50">
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>{status.replace(/_/g, ' ')}</span>
        <span>{progress.toFixed(0)}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

export default function AnalysisLayout() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const { data: project, isLoading, error } = useQuery<Project>({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId!),
    refetchInterval: (query) => {
      const p = query.state.data
      if (!p) return 5000
      const done = ['COMPLETED', 'FAILED', 'PARTIAL']
      return done.includes(p.status) ? false : 4000
    },
    enabled: !!projectId,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400">
          <Loader2 size={20} className="animate-spin text-brand-400" />
          Loading project...
        </div>
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-surface-950 flex flex-col items-center justify-center gap-4">
        <AlertCircle size={40} className="text-red-400" />
        <p className="text-slate-300">Project not found</p>
        <button onClick={() => navigate('/projects')} className="btn-secondary">
          Back to Projects
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface-950 flex flex-col">
      {/* Top header */}
      <header className="border-b border-surface-800 bg-surface-950/95 backdrop-blur-xl sticky top-0 z-30 h-14 flex items-center">
        <div className="flex items-center h-full w-full px-4 gap-4">
          <button
            onClick={() => navigate('/projects')}
            className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors text-sm"
          >
            <ChevronLeft size={15} /> Projects
          </button>
          <div className="h-4 w-px bg-surface-700" />
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="w-7 h-7 rounded-md bg-gradient-to-br from-brand-500 to-purple-600 
                            flex items-center justify-center flex-shrink-0">
              <Brain size={14} className="text-white" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-100 truncate">{project.name}</div>
              <div className="text-xs text-slate-500 truncate">{project.project_type || 'Analyzing...'}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Status badge */}
            <div className={`badge ${
              project.status === 'COMPLETED' ? 'badge-completed' :
              project.status === 'FAILED' ? 'badge-failed' :
              project.status === 'PARTIAL' ? 'badge-uncertain' :
              'badge-running'
            }`}>
              {['COMPLETED','FAILED','PARTIAL'].includes(project.status) ? null : 
                <Loader2 size={10} className="animate-spin" />
              }
              {project.status.replace(/_/g, ' ')}
            </div>
            {/* Quick stats */}
            <div className="hidden lg:flex items-center gap-4 text-xs text-slate-400">
              <span><span className="font-semibold text-slate-200">{project.total_files}</span> files</span>
              <span><span className="font-semibold text-slate-200">{project.total_classes}</span> classes</span>
              <span><span className="font-semibold text-slate-200">{project.total_functions}</span> functions</span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <nav className="w-56 flex-shrink-0 border-r border-surface-800 bg-surface-900/50 
                        flex flex-col overflow-y-auto no-scrollbar">
          {/* Progress indicator */}
          <ProgressBar progress={project.analysis_progress} status={project.status} />

          <div className="p-3 flex-1">
            <p className="px-3 pt-2 pb-1 text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
              Analysis
            </p>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.path}
                to={`/analysis/${projectId}/${item.path}`}
                className={({ isActive }) =>
                  isActive ? 'nav-item-active mb-0.5 block' : 'nav-item-inactive mb-0.5 block'
                }
              >
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-surface-700/50">
            <div className="text-xs text-slate-500">
              {project.primary_language && (
                <div className="flex items-center gap-1.5 mb-1">
                  <div className={`w-2 h-2 rounded-full ${
                    project.primary_language === 'Python' ? 'bg-blue-400' :
                    project.primary_language === 'JavaScript' ? 'bg-yellow-400' :
                    project.primary_language === 'TypeScript' ? 'bg-blue-500' :
                    project.primary_language === 'Java' ? 'bg-orange-500' : 'bg-slate-400'
                  }`} />
                  {project.primary_language}
                </div>
              )}
              <div className="text-slate-600 truncate text-[10px]">{project.id.slice(0, 8)}...</div>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="min-h-full p-6">
            <Outlet context={project} />
          </div>
        </main>
      </div>
    </div>
  )
}
