import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LandingPage from './pages/LandingPage'
import ProjectsPage from './pages/ProjectsPage'
import AnalysisLayout from './layouts/AnalysisLayout'
import DashboardPage from './pages/analysis/DashboardPage'
import ArchitecturePage from './pages/analysis/ArchitecturePage'
import CallGraphPage from './pages/analysis/CallGraphPage'
import CodeExplorerPage from './pages/analysis/CodeExplorerPage'
import SlicingPage from './pages/analysis/SlicingPage'
import TracingPage from './pages/analysis/TracingPage'
import UMLPage from './pages/analysis/UMLPage'
import VerificationPage from './pages/analysis/VerificationPage'
import AskAIPage from './pages/analysis/AskAIPage'
import ReportPage from './pages/analysis/ReportPage'
import ChangeImpactPage from './pages/analysis/ChangeImpactPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  React.useEffect(() => {
    document.documentElement.classList.add('dark')
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/analysis/:projectId" element={<AnalysisLayout />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="architecture" element={<ArchitecturePage />} />
            <Route path="call-graph" element={<CallGraphPage />} />
            <Route path="code" element={<CodeExplorerPage />} />
            <Route path="slicing" element={<SlicingPage />} />
            <Route path="tracing" element={<TracingPage />} />
            <Route path="uml" element={<UMLPage />} />
            <Route path="verification" element={<VerificationPage />} />
            <Route path="ask" element={<AskAIPage />} />
            <Route path="report" element={<ReportPage />} />
            <Route path="impact" element={<ChangeImpactPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
