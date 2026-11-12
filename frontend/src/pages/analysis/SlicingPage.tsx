import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Scissors, Loader2, ChevronRight, FileCode } from 'lucide-react'
import { createSlice } from '../../api/client'
import type { Project } from '../../store/appStore'

const SLICE_TYPES = ['forward', 'backward', 'feature', 'function']

export default function SlicingPage() {
  const project = useOutletContext<Project>()
  const [criterion, setCriterion] = useState('')
  const [sliceType, setSliceType] = useState('forward')

  const mutation = useMutation({
    mutationFn: () => createSlice(project.id, criterion, sliceType),
  })

  return (
    <div className="space-y-5 animate-fade-in max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Scissors size={22} className="text-brand-400" />
          Program Slicing
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Hierarchical program slicing from function → class → module → behavior level.
        </p>
      </div>

      <div className="card p-5">
        <div className="grid md:grid-cols-3 gap-3 mb-4">
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Slice Criterion</label>
            <input
              className="input w-full"
              placeholder="Function name, class, or variable (e.g., login, UserService)"
              value={criterion}
              onChange={(e) => setCriterion(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Slice Type</label>
            <select
              className="input w-full"
              value={sliceType}
              onChange={(e) => setSliceType(e.target.value)}
            >
              {SLICE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
            </select>
          </div>
        </div>
        <button
          className="btn-primary"
          disabled={!criterion.trim() || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Scissors size={15} />}
          Compute Slice
        </button>
      </div>

      {mutation.data && (
        <div className="space-y-4 animate-fade-in">
          <div className="card p-5">
            <h3 className="section-title mb-3">Explanation</h3>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{mutation.data.explanation}</p>
          </div>

          {mutation.data.dependency_path?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">Dependency Path</h3>
              <div className="flex items-center flex-wrap gap-1.5">
                {mutation.data.dependency_path.map((node: string, i: number) => (
                  <React.Fragment key={i}>
                    <span className="tag text-brand-300 bg-brand-600/10 border-brand-600/30 font-mono">{node}</span>
                    {i < mutation.data.dependency_path.length - 1 && <ChevronRight size={13} className="text-slate-500" />}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {mutation.data.relevant_files?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">Relevant Files ({mutation.data.relevant_files.length})</h3>
              <div className="space-y-1.5">
                {mutation.data.relevant_files.map((f: string) => (
                  <div key={f} className="evidence-item">
                    <FileCode size={13} className="text-brand-400" />
                    <span className="font-mono text-sm text-slate-300">{f}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {mutation.data.source_lines?.length > 0 && (
            <div className="card p-5">
              <h3 className="section-title mb-3">Program Elements in Slice</h3>
              <div className="space-y-2">
                {mutation.data.source_lines.map((line: any, i: number) => (
                  <div key={i} className="evidence-item">
                    <div>
                      <div className="text-xs font-mono text-slate-300">
                        {line.file}:{line.line_start}{line.line_end ? `-${line.line_end}` : ''}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {line.type}: <span className="text-brand-300 font-semibold">{line.symbol}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {mutation.isError && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {(mutation.error as Error).message}
        </div>
      )}
    </div>
  )
}
