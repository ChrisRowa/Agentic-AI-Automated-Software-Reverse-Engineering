import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { 
  Plus, Upload, Brain, Trash2, ExternalLink, 
  Clock, CheckCircle2, AlertCircle, Loader2, 
  FileArchive, Code2, ChevronRight, RefreshCw,
  FolderOpen, BarChart3, Database, Layers
} from 'lucide-react'
import { listProjects, createProject, uploadRepository, deleteProject } from '../api/client'
import type { Project } from '../store/appStore'

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  QUEUED:          { color: 'badge-queued',    icon: <Clock size={10}/>,       label: 'Queued' },
  EXTRACTING:      { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'Extracting' },
  DISCOVERING:     { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'Discovering' },
  PARSING:         { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'Parsing' },
  BUILDING_GRAPHS: { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'Building Graphs' },
  INDEXING:        { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'Indexing' },
  AGENT_ANALYSIS:  { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'AI Analysis' },
  VERIFYING:       { color: 'badge-running',   icon: <Loader2 size={10} className="animate-spin"/>, label: 'Verifying' },
  COMPLETED:       { color: 'badge-completed', icon: <CheckCircle2 size={10}/>, label: 'Completed' },
  FAILED:          { color: 'badge-failed',    icon: <AlertCircle size={10}/>, label: 'Failed' },
  PARTIAL:         { color: 'badge-uncertain', icon: <AlertCircle size={10}/>, label: 'Partial' },
}

function UploadModal({ projectId, onClose, onComplete }: {
  projectId: string; onClose: () => void; onComplete: () => void
}) {
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Only ZIP files are supported')
      return
    }
    setUploading(true)
    setError('')
    try {
      await uploadRepository(projectId, file, setUploadProgress)
      onComplete()
    } catch (e: any) {
      setError(e.message)
      setUploading(false)
    }
  }, [projectId, onComplete])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'application/zip': ['.zip'] }, maxFiles: 1, disabled: uploading
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-lg mx-4 p-8 animate-fade-in">
        <h2 className="text-xl font-bold text-slate-100 mb-2">Upload Repository</h2>
        <p className="text-sm text-slate-400 mb-6">
          Upload a ZIP archive of your source code. Maximum {100}MB.
        </p>

        {!uploading ? (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
              ${isDragActive 
                ? 'border-brand-500 bg-brand-600/10' 
                : 'border-surface-600 hover:border-brand-500/60 hover:bg-surface-700/30'}`}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-3">
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-colors
                ${isDragActive ? 'bg-brand-600/20' : 'bg-surface-700'}`}>
                <FileArchive size={28} className={isDragActive ? 'text-brand-400' : 'text-slate-400'} />
              </div>
              <div>
                <p className="text-slate-200 font-medium">
                  {isDragActive ? 'Drop your ZIP here' : 'Drag & drop ZIP file'}
                </p>
                <p className="text-sm text-slate-400 mt-1">or click to browse</p>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {['Python', 'JavaScript', 'TypeScript', 'Java'].map(l => (
                  <span key={l} className="tag">{l}</span>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="py-8">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-slate-300 font-medium">
                {uploadProgress < 100 ? 'Uploading...' : 'Processing...'}
              </span>
              <span className="text-sm font-bold text-brand-400">{uploadProgress}%</span>
            </div>
            <div className="progress-bar mb-6">
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
            <div className="flex items-center gap-2 text-slate-400 text-sm justify-center">
              <Loader2 size={14} className="animate-spin" />
              Analysis pipeline started — you can track progress in the dashboard
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="flex gap-3 mt-6">
          {!uploading && (
            <button onClick={onClose} className="btn-secondary flex-1">Cancel</button>
          )}
        </div>
      </div>
    </div>
  )
}

function ProjectCard({ project, onOpen, onDelete }: {
  project: Project; onOpen: () => void; onDelete: () => void
}) {
  const cfg = STATUS_CONFIG[project.status] || STATUS_CONFIG.QUEUED
  const isRunning = !['COMPLETED', 'FAILED', 'PARTIAL', 'QUEUED'].includes(project.status)

  return (
    <div className="card-hover p-6 group cursor-pointer" onClick={onOpen}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-100 truncate pr-4">{project.name}</h3>
          {project.original_filename && (
            <p className="text-xs text-slate-500 mt-0.5 truncate">{project.original_filename}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={cfg.color + ' gap-1 flex items-center'}>
            {cfg.icon} {cfg.label}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-red-500/20 
                       hover:text-red-400 text-slate-500 transition-all"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      {isRunning && (
        <div className="mb-4">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${project.analysis_progress}%` }} />
          </div>
          <p className="text-xs text-slate-500 mt-1">{project.analysis_progress.toFixed(0)}% complete</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[
          { icon: <Code2 size={12}/>, label: 'Files', value: project.total_files },
          { icon: <Layers size={12}/>, label: 'Classes', value: project.total_classes },
          { icon: <BarChart3 size={12}/>, label: 'Functions', value: project.total_functions },
        ].map((s) => (
          <div key={s.label} className="text-center p-2 bg-surface-900/60 rounded-lg">
            <div className="flex items-center justify-center gap-1 text-slate-400 mb-1">
              {s.icon}
              <span className="text-[10px] font-medium uppercase tracking-wide">{s.label}</span>
            </div>
            <div className="text-sm font-bold text-slate-200">{s.value.toLocaleString()}</div>
          </div>
        ))}
      </div>

      {/* Language tags */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {project.primary_language && (
          <span className="tag">{project.primary_language}</span>
        )}
        {(project.detected_frameworks || []).slice(0, 2).map(fw => (
          <span key={fw} className="tag">{fw}</span>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">
          {new Date(project.created_at).toLocaleDateString()}
        </span>
        {project.status === 'COMPLETED' && (
          <div className="flex items-center gap-1 text-xs text-brand-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
            Open Analysis <ChevronRight size={12} />
          </div>
        )}
      </div>
    </div>
  )
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [uploadProjectId, setUploadProjectId] = useState<string | null>(null)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: () => listProjects(),
    refetchInterval: 5000, // Poll every 5s for running analyses
  })

  const createMutation = useMutation({
    mutationFn: ({ name }: { name: string }) => createProject(name),
    onSuccess: (project: any) => {
      setProjectName('')
      setShowNew(false)
      setUploadProjectId(project?.id || ('proj-' + Date.now()))
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
    onError: (err: any) => {
      console.warn('Project creation error, opening upload modal', err)
      setProjectName('')
      setShowNew(false)
      setUploadProjectId('proj-' + Date.now())
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  })

  const projects: Project[] = data?.projects || []

  return (
    <div className="min-h-screen bg-surface-950">
      {/* Header */}
      <header className="border-b border-surface-800 bg-surface-950/90 backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-purple-600 
                            flex items-center justify-center shadow-glow-sm">
              <Brain size={16} className="text-white" />
            </div>
            <span className="font-bold text-slate-100">ReverseAI</span>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => refetch()} className="btn-ghost p-2">
              <RefreshCw size={15} />
            </button>
            <button
              onClick={() => setShowNew(true)}
              className="btn-primary"
            >
              <Plus size={16} /> New Analysis
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Title */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-100">Projects</h1>
          <p className="text-slate-400 mt-1">
            Upload and analyze software repositories
          </p>
        </div>

        {/* New project form */}
        {showNew && (
          <div className="card p-6 mb-6 border-brand-600/30 animate-fade-in">
            <h3 className="font-semibold text-slate-100 mb-4">Create New Project</h3>
            <div className="flex gap-3">
              <input
                className="input flex-1"
                placeholder="Project name (e.g., Banking App Analysis)"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && projectName.trim() && createMutation.mutate({ name: projectName.trim() })}
                autoFocus
              />
              <button
                className="btn-primary"
                disabled={!projectName.trim() || createMutation.isPending}
                onClick={() => createMutation.mutate({ name: projectName.trim() })}
              >
                {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ChevronRight size={16} />}
                Create
              </button>
              <button onClick={() => setShowNew(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}

        {/* Projects grid */}
        {isLoading ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="card p-6 h-52 skeleton" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-20 h-20 rounded-2xl bg-surface-800 border border-surface-700 
                            flex items-center justify-center mb-6">
              <FolderOpen size={36} className="text-slate-500" />
            </div>
            <h3 className="text-xl font-semibold text-slate-300 mb-2">No Projects Yet</h3>
            <p className="text-slate-500 mb-8 max-w-md">
              Create a new project and upload a ZIP file to start analyzing a repository.
            </p>
            <button onClick={() => setShowNew(true)} className="btn-primary">
              <Plus size={16} /> Create Your First Project
            </button>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onOpen={() => {
                  if (project.status === 'QUEUED') {
                    setUploadProjectId(project.id)
                  } else {
                    navigate(`/analysis/${project.id}/dashboard`)
                  }
                }}
                onDelete={() => {
                  if (confirm('Delete this project and all its analysis data?')) {
                    deleteMutation.mutate(project.id)
                  }
                }}
              />
            ))}
          </div>
        )}
      </main>

      {/* Upload modal */}
      {uploadProjectId && (
        <UploadModal
          projectId={uploadProjectId}
          onClose={() => setUploadProjectId(null)}
          onComplete={() => {
            setUploadProjectId(null)
            queryClient.invalidateQueries({ queryKey: ['projects'] })
            navigate(`/analysis/${uploadProjectId}/dashboard`)
          }}
        />
      )}
    </div>
  )
}
