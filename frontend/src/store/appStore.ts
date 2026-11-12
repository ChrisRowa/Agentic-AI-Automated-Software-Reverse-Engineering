import { create } from 'zustand'

export interface Project {
  id: string
  name: string
  description?: string
  status: string
  created_at: string
  updated_at?: string
  completed_at?: string
  original_filename?: string
  archive_size_bytes?: number
  file_count?: number
  primary_language?: string
  detected_languages?: Record<string, number>
  detected_frameworks?: string[]
  project_type?: string
  total_files: number
  total_classes: number
  total_functions: number
  total_modules: number
  total_dependencies: number
  total_api_endpoints: number
  total_lines_of_code: number
  analysis_progress: number
  error_message?: string
  git_available: boolean
}

interface AppState {
  // Projects
  projects: Project[]
  currentProject: Project | null
  setProjects: (projects: Project[]) => void
  setCurrentProject: (project: Project | null) => void
  updateProjectStatus: (id: string, updates: Partial<Project>) => void

  // UI state
  sidebarCollapsed: boolean
  setSidebarCollapsed: (v: boolean) => void
  activeView: string
  setActiveView: (view: string) => void

  // Theme
  theme: 'dark' | 'light'
  toggleTheme: () => void
}

export const useAppStore = create<AppState>((set) => ({
  projects: [],
  currentProject: null,
  setProjects: (projects) => set({ projects }),
  setCurrentProject: (project) => set({ currentProject: project }),
  updateProjectStatus: (id, updates) =>
    set((state) => ({
      projects: state.projects.map((p) => (p.id === id ? { ...p, ...updates } : p)),
      currentProject:
        state.currentProject?.id === id
          ? { ...state.currentProject, ...updates }
          : state.currentProject,
    })),

  sidebarCollapsed: false,
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  activeView: 'dashboard',
  setActiveView: (view) => set({ activeView: view }),

  theme: 'dark',
  toggleTheme: () =>
    set((state) => {
      const newTheme = state.theme === 'dark' ? 'light' : 'dark'
      document.documentElement.classList.toggle('dark', newTheme === 'dark')
      return { theme: newTheme }
    }),
}))
