import React from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Brain, Upload, GitBranch, Code2, Network, Shield, 
  ChevronRight, Zap, Eye, FileSearch, ArrowRight,
  CheckCircle2, Layers, GitGraph
} from 'lucide-react'

const FEATURES = [
  { icon: <GitGraph size={20}/>, title: 'Program Knowledge Graph', desc: 'Builds a structured graph of your entire codebase — files, classes, functions, dependencies.' },
  { icon: <Brain size={20}/>, title: 'LangGraph Multi-Agent AI', desc: 'Specialized agents for code understanding, UML, slicing, traceability, and verification.' },
  { icon: <Shield size={20}/>, title: 'Evidence-Based Verification', desc: 'Every AI claim is verified against actual source code. No hallucination.' },
  { icon: <Layers size={20}/>, title: 'Hierarchical Reconstruction', desc: 'Understand software at every level: function → class → module → system.' },
  { icon: <FileSearch size={20}/>, title: 'Hybrid RAG Retrieval', desc: 'Semantic + lexical + graph retrieval for precise, context-aware answers.' },
  { icon: <Eye size={20}/>, title: 'Program Slicing', desc: 'Forward, backward, and feature slices to trace how features are implemented.' },
]

const WORKFLOW = [
  { step: '01', label: 'Upload Repository', desc: 'ZIP file or Git repo' },
  { step: '02', label: 'Static Analysis', desc: 'AST, call graph, dependencies' },
  { step: '03', label: 'Knowledge Graph', desc: 'Build program representation' },
  { step: '04', label: 'Agent Analysis', desc: 'Multi-agent AI reasoning' },
  { step: '05', label: 'Verification', desc: 'Evidence-backed results' },
  { step: '06', label: 'Report', desc: 'System Reconstruction Report' },
]

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-surface-950 overflow-hidden">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-surface-800/50 backdrop-blur-xl bg-surface-950/80">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center shadow-glow-sm">
              <Brain size={16} className="text-white" />
            </div>
            <span className="font-bold text-slate-100">ReverseAI</span>
          </div>
          <nav className="hidden md:flex items-center gap-6 text-sm text-slate-400">
            <a href="#features" className="hover:text-slate-200 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-slate-200 transition-colors">How It Works</a>
            <button onClick={() => navigate('/projects')} className="btn-primary">
              Get Started
            </button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative pt-32 pb-24 px-6">
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[400px] 
                          bg-brand-600/10 blur-[120px] rounded-full" />
        </div>

        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full 
                          bg-brand-600/15 border border-brand-600/30 text-brand-300 text-xs font-medium mb-8">
            <Zap size={12} />
            Final Year Engineering Project — AIML
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold text-slate-50 leading-tight mb-6">
            Automated Software
            <span className="block text-gradient glow-text">Reverse Engineering</span>
            <span className="block text-4xl md:text-5xl font-bold text-slate-300 mt-2">Powered by Agentic AI</span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-3xl mx-auto mb-10 leading-relaxed">
            Upload any repository. Get an evidence-backed System Reconstruction Report — 
            architecture, call graphs, dependency analysis, program slices, UML diagrams, 
            and AI explanations, all grounded in actual source code.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => navigate('/projects')}
              className="btn-primary px-8 py-3 text-base gap-3 shadow-glow"
            >
              <Upload size={18} />
              Analyze Repository
              <ChevronRight size={16} />
            </button>
            <button
              onClick={() => navigate('/projects')}
              className="btn-secondary px-8 py-3 text-base"
            >
              View Projects
            </button>
          </div>

"          {/* Stats row */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-3 gap-4 max-w-3xl mx-auto">
            {[
              { label: 'Languages Supported', value: '4+' },
              { label: 'Analysis Agents', value: '12' },
              { label: 'Evidence-Grounded', value: '100%' },
            ].map((s) => (
              <div key={s.label} className="card-glass p-4 text-center">
                <div className="text-2xl font-bold text-gradient">{s.value}</div>
                <div className="text-xs text-slate-400 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-100 mb-4">
              Core System Capabilities
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Combining traditional program analysis, static graphs, and multi-agent AI for automated software reverse engineering.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map((f) => (
              <div key={f.title} className="card-hover p-6 group">
                <div className="w-10 h-10 rounded-lg bg-brand-600/15 border border-brand-600/25 
                                flex items-center justify-center text-brand-400 mb-4
                                group-hover:bg-brand-600/25 transition-colors">
                  {f.icon}
                </div>
                <h3 className="font-semibold text-slate-100 mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section id="how-it-works" className="py-24 px-6 bg-gradient-to-b from-transparent to-surface-900/40">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-100 mb-4">
              How It Works
            </h2>
            <p className="text-slate-400">
              From repository upload to System Reconstruction Report in minutes.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {WORKFLOW.map((w, i) => (
              <div key={w.step} className="relative">
                <div className="card p-6">
                  <div className="text-3xl font-black text-brand-600/30 mb-3">{w.step}</div>
                  <div className="font-semibold text-slate-100 mb-1">{w.label}</div>
                  <div className="text-sm text-slate-400">{w.desc}</div>
                </div>
                {i < WORKFLOW.length - 1 && (
                  <div className="hidden md:flex absolute top-1/2 -right-2 z-10 
                                  items-center justify-center w-4 h-4 
                                  text-brand-500 -translate-y-1/2">
                    <ArrowRight size={14} />
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-12 text-center">
            <button
              onClick={() => navigate('/projects')}
              className="btn-primary px-10 py-3 text-base shadow-glow"
            >
              Start Your First Analysis
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* Evidence box */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="card p-8 bg-gradient-to-br from-surface-800 to-surface-900 border-brand-600/20">
            <div className="flex items-start gap-6">
              <div className="w-12 h-12 rounded-xl bg-brand-600/20 border border-brand-600/30 
                              flex items-center justify-center text-brand-400 flex-shrink-0">
                <Shield size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-100 mb-2">
                  No Evidence → No Factual Claim
                </h3>
                <p className="text-slate-400 mb-4">
                  Unlike generic AI tools, every factual statement in ReverseAI is linked to 
                  actual source code. Our verification engine classifies all AI-generated claims:
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="badge-verified justify-center py-2">✓ Verified</div>
                  <div className="badge-inferred justify-center py-2">~ Inferred</div>
                  <div className="badge-uncertain justify-center py-2">? Uncertain</div>
                  <div className="badge-unsupported justify-center py-2">✗ Unsupported</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-800 py-10 px-6 text-center text-slate-500 text-sm">
        <div className="flex items-center justify-center gap-2 mb-2">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-brand-500 to-purple-600 
                          flex items-center justify-center">
            <Brain size={12} className="text-white" />
          </div>
          <span className="font-medium text-slate-400">ReverseAI</span>
        </div>
        <p>Agentic AI-Based Automated Software Reverse Engineering — Final Year Engineering Project</p>
      </footer>
    </div>
  )
}
