import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Send, Brain, AlertCircle, Loader2, FileCode, ChevronRight, Shield } from 'lucide-react'
import { askQuestion } from '../../api/client'
import type { Project } from '../../store/appStore'

interface Message {
  id: string
  type: 'user' | 'ai'
  content: string
  evidence?: any[]
  call_path?: string[]
  relevant_files?: string[]
  confidence?: number
  verification_status?: string
  intent_type?: string
}

const SAMPLE_QUESTIONS = [
  'What does this software do?',
  'How does the authentication work?',
  'What are the main modules?',
  'Which functions handle database operations?',
  'Explain the data flow for user login',
]

const VERIFICATION_BADGE: Record<string, string> = {
  VERIFIED: 'badge-verified',
  INFERRED: 'badge-inferred',
  UNCERTAIN: 'badge-uncertain',
  UNSUPPORTED: 'badge-unsupported',
}

export default function AskAIPage() {
  const project = useOutletContext<Project>()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')

  const mutation = useMutation({
    mutationFn: (question: string) => askQuestion(project.id, question),
    onSuccess: (data, question) => {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 'a', type: 'user', content: question },
        {
          id: Date.now() + 'b',
          type: 'ai',
          content: data.answer,
          evidence: data.evidence,
          call_path: data.call_path,
          relevant_files: data.relevant_files,
          confidence: data.confidence,
          verification_status: data.verification_status,
          intent_type: data.intent_type,
        },
      ])
    },
  })

  const handleSend = (q: string) => {
    const question = q.trim()
    if (!question || mutation.isPending) return
    setInput('')
    mutation.mutate(question)
  }

  const notReady = !['COMPLETED', 'PARTIAL'].includes(project.status)

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] animate-fade-in">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Brain size={22} className="text-brand-400" />
          Ask AI
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Evidence-backed answers from your repository. Every response is grounded in actual source code.
        </p>
      </div>

      {notReady ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 size={32} className="text-brand-400 animate-spin mx-auto mb-3" />
            <p className="text-slate-400">Analysis must complete before asking questions.</p>
          </div>
        </div>
      ) : (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 mb-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-6 py-12">
                <div className="w-16 h-16 rounded-2xl bg-brand-600/15 border border-brand-600/25 
                                flex items-center justify-center">
                  <Brain size={28} className="text-brand-400" />
                </div>
                <div className="text-center">
                  <h3 className="text-lg font-semibold text-slate-200 mb-2">Ask About Your Repository</h3>
                  <p className="text-slate-400 text-sm max-w-md">
                    Ask any question about the code. Answers are grounded in evidence 
                    from static analysis and the program knowledge graph.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-2 w-full max-w-lg">
                  {SAMPLE_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSend(q)}
                      className="text-left px-4 py-2.5 rounded-lg bg-surface-800 border border-surface-700
                                 hover:border-brand-600/40 hover:bg-surface-700/80 text-slate-300 text-sm
                                 transition-all flex items-center justify-between group"
                    >
                      {q}
                      <ChevronRight size={14} className="text-slate-500 group-hover:text-brand-400 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.type === 'user' ? (
                    <div className="max-w-[80%] px-4 py-3 rounded-2xl bg-brand-600 text-white text-sm">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="max-w-[90%] space-y-3">
                      <div className="card p-4">
                        {/* Header */}
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-6 h-6 rounded-md bg-brand-600/20 flex items-center justify-center">
                            <Brain size={12} className="text-brand-400" />
                          </div>
                          <span className="text-xs font-medium text-slate-400">ReverseAI</span>
                          {msg.verification_status && (
                            <span className={VERIFICATION_BADGE[msg.verification_status] || 'badge-uncertain'}>
                              {msg.verification_status}
                            </span>
                          )}
                          {msg.intent_type && (
                            <span className="tag text-[10px]">{msg.intent_type}</span>
                          )}
                          {msg.confidence !== undefined && (
                            <span className="text-xs text-slate-500 ml-auto">
                              Confidence: {(msg.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>

                        {/* Answer */}
                        <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                          {msg.content}
                        </div>

                        {/* Call path */}
                        {msg.call_path && msg.call_path.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-surface-700/50">
                            <p className="text-xs font-medium text-slate-400 mb-2">Call Path:</p>
                            <div className="flex items-center gap-1 flex-wrap">
                              {msg.call_path.map((step, i) => (
                                <React.Fragment key={i}>
                                  <span className="tag text-brand-300 border-brand-600/30 bg-brand-600/10">
                                    {step}
                                  </span>
                                  {i < msg.call_path!.length - 1 && (
                                    <ChevronRight size={12} className="text-slate-500" />
                                  )}
                                </React.Fragment>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Evidence */}
                        {msg.evidence && msg.evidence.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-surface-700/50">
                            <p className="text-xs font-medium text-slate-400 mb-2 flex items-center gap-1">
                              <Shield size={11} className="text-brand-400" />
                              Evidence ({msg.evidence.length} sources)
                            </p>
                            <div className="space-y-1.5">
                              {msg.evidence.slice(0, 5).map((ev, i) => (
                                <div key={i} className="evidence-item">
                                  <FileCode size={13} className="text-brand-400 mt-0.5 flex-shrink-0" />
                                  <div className="min-w-0">
                                    <div className="text-xs font-mono text-slate-300 truncate">
                                      {ev.file}
                                      {ev.line_start && `:${ev.line_start}`}
                                      {ev.line_end && `-${ev.line_end}`}
                                    </div>
                                    {ev.content_snippet && (
                                      <div className="text-xs text-slate-500 mt-0.5 truncate">
                                        {ev.content_snippet}
                                      </div>
                                    )}
                                  </div>
                                  <span className="tag flex-shrink-0 text-[10px]">{ev.evidence_type}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Relevant files */}
                        {msg.relevant_files && msg.relevant_files.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-surface-700/50">
                            <p className="text-xs font-medium text-slate-400 mb-1.5">Relevant Files:</p>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.relevant_files.slice(0, 8).map((f) => (
                                <span key={f} className="tag font-mono text-[10px]">{f.split('/').pop()}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
            {mutation.isPending && (
              <div className="flex justify-start">
                <div className="card px-5 py-4">
                  <div className="flex items-center gap-2 text-slate-400 text-sm">
                    <Loader2 size={14} className="animate-spin text-brand-400" />
                    Retrieving evidence and reasoning...
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="flex gap-3">
            <input
              className="input flex-1"
              placeholder="Ask about your repository..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend(input)}
              disabled={mutation.isPending}
            />
            <button
              onClick={() => handleSend(input)}
              disabled={!input.trim() || mutation.isPending}
              className="btn-primary"
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
