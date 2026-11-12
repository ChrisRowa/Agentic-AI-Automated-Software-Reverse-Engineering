import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Code2, ChevronRight, Loader2, FileCode, Search } from 'lucide-react'
import { getFiles, getFileContent } from '../../api/client'
import type { Project } from '../../store/appStore'
import SyntaxHighlighter from 'react-syntax-highlighter'
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs'

const LANG_MAP: Record<string, string> = {
  Python: 'python', JavaScript: 'javascript', TypeScript: 'typescript',
  Java: 'java', 'C#': 'csharp', Go: 'go', Rust: 'rust', CSS: 'css', HTML: 'html',
}

export default function CodeExplorerPage() {
  const project = useOutletContext<Project>()
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const { data: files = [] } = useQuery({
    queryKey: ['files', project.id],
    queryFn: () => getFiles(project.id, { limit: 500 }),
    enabled: ['COMPLETED', 'PARTIAL'].includes(project.status),
  })

  const { data: fileContent, isLoading: contentLoading } = useQuery({
    queryKey: ['file-content', project.id, selectedFileId],
    queryFn: () => getFileContent(project.id, selectedFileId!),
    enabled: !!selectedFileId,
  })

  const filtered = files.filter((f: any) =>
    !search || f.relative_path.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="animate-fade-in">
      <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2 mb-4">
        <Code2 size={22} className="text-brand-400" />
        Code Explorer
      </h1>

      <div className="grid grid-cols-12 gap-4 h-[calc(100vh-12rem)]">
        {/* File tree */}
        <div className="col-span-4 card flex flex-col overflow-hidden">
          <div className="p-3 border-b border-surface-700/50">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                className="input w-full pl-9 text-xs"
                placeholder="Search files..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-2 no-scrollbar">
            {filtered.map((f: any) => (
              <button
                key={f.id}
                onClick={() => setSelectedFileId(f.id)}
                className={`w-full text-left px-3 py-2 rounded-lg mb-0.5 text-xs transition-colors
                  ${selectedFileId === f.id
                    ? 'bg-brand-600/20 text-brand-300 border border-brand-600/30'
                    : 'text-slate-400 hover:bg-surface-700/50 hover:text-slate-200'}`}
              >
                <div className="flex items-center gap-2">
                  <FileCode size={12} className="flex-shrink-0 text-slate-500" />
                  <span className="truncate font-mono">{f.relative_path}</span>
                </div>
                {f.language && (
                  <div className="ml-5 mt-0.5 text-[10px] text-slate-500">{f.language} · {f.lines_of_code} lines</div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Code viewer */}
        <div className="col-span-8 card overflow-hidden flex flex-col">
          {!selectedFileId ? (
            <div className="flex-1 flex items-center justify-center text-slate-500">
              <div className="text-center">
                <FileCode size={32} className="mx-auto mb-2 text-slate-600" />
                <p className="text-sm">Select a file to view its source</p>
              </div>
            </div>
          ) : contentLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 size={20} className="animate-spin text-brand-400" />
            </div>
          ) : fileContent ? (
            <div className="flex flex-col h-full overflow-hidden">
              <div className="px-4 py-2 border-b border-surface-700/50 flex items-center gap-2">
                <FileCode size={13} className="text-brand-400" />
                <span className="text-xs font-mono text-slate-300">{fileContent.relative_path}</span>
                <span className="tag ml-auto">{fileContent.language}</span>
                <span className="text-xs text-slate-500">{fileContent.lines} lines</span>
              </div>
              <div className="flex-1 overflow-auto">
                <SyntaxHighlighter
                  language={LANG_MAP[fileContent.language] || 'text'}
                  style={atomOneDark}
                  showLineNumbers
                  lineNumberStyle={{ color: '#475569', fontSize: '11px' }}
                  customStyle={{ background: '#0f172a', margin: 0, fontSize: '12px', height: '100%' }}
                >
                  {fileContent.content}
                </SyntaxHighlighter>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
