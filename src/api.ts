import type { AIStatus, AISummary, Analysis, Backup, Bootstrap, CalendarData, CoachTip, CompanyDetail, CompanySummary, Draft, EmailEvent, Fact, GitHubProject, GitHubRepo, Job, JobDetail, PrepPack, SearchResult, SourceInfo, TailorResult, UpdateState, Validation } from './types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`)
  return body as T
}

const post = <T = unknown>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })
const remove = (path: string) => request<{ ok: boolean }>(path, { method: 'DELETE', body: '{}' })

export const api = {
  bootstrap: () => request<Bootstrap>('/api/bootstrap'),
  health: () => request<{ status: string; version: string; database: string }>('/health'),
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  saveFact: (fact: Fact) => post<Fact>('/api/profile/facts', fact),
  deleteFact: (id: string) => remove(`/api/profile/facts/${id}`),
  saveAnswer: (answer: Record<string, unknown>) => post<{ id: string; status: string }>('/api/answers', answer),
  approveAnswer: (id: string) => post(`/api/answers/${id}/approve`),
  deleteAnswer: (id: string) => remove(`/api/answers/${id}`),
  settings: (settings: Record<string, unknown>) => post('/api/settings', settings),
  importJob: (url: string) => post<Job>('/api/jobs/import', { url }),
  manualJob: (job: Record<string, unknown>) => post<Job>('/api/jobs/manual', job),
  deleteJob: (id: string) => remove(`/api/jobs/${id}`),
  analyzeJob: (id: string) => post<Analysis>(`/api/jobs/${id}/analyze`),
  analyzeAll: () => post<{ analyzed: number }>('/api/jobs/analyze-all'),
  queueJob: (id: string) => post<{ id: string; status: string }>(`/api/jobs/${id}/queue`),
  voteJob: (id: string, vote: -1 | 0 | 1) => post<{ votes: number; learning: boolean }>(`/api/jobs/${id}/vote`, { vote }),
  summarize: (id: string) => post<AISummary>(`/api/jobs/${id}/summary`),
  coverLetter: (id: string) => post<Draft>(`/api/jobs/${id}/cover-letter`),
  tailor: (id: string, ai: boolean) => post<TailorResult>(`/api/jobs/${id}/tailor`, { ai }),
  tailoredDiff: (draftId: string) => request<TailorResult>(`/api/drafts/${draftId}/diff`),
  prep: (id: string) => request<PrepPack>(`/api/jobs/${id}/prep`),
  referral: (jobId: string, connectionId: string) => post<{ message: string; url?: string }>(`/api/jobs/${jobId}/referral`, { connection_id: connectionId }),
  search: (q: string) => request<SearchResult>(`/api/search?q=${encodeURIComponent(q)}`),
  insights: () => request<{ coach: CoachTip[] }>('/api/insights'),
  companies: () => request<CompanySummary[]>('/api/companies'),
  company: (key: string) => request<CompanyDetail>(`/api/companies/${encodeURIComponent(key)}`),
  companyNotes: (key: string, name: string, notes: string) => post(`/api/companies/${encodeURIComponent(key)}/notes`, { name, notes }),
  importConnections: (csv: string) => post<{ connections: number; matched_companies: number }>('/api/connections/import', { csv }),
  clearConnections: () => post('/api/connections/clear'),
  calendar: () => request<CalendarData>('/api/calendar'),
  saveOffer: (offer: Record<string, unknown>) => post<{ id: string }>('/api/offers', offer),
  deleteOffer: (id: string) => remove(`/api/offers/${id}`),
  importCV: (filename: string, content_base64: string) => post<{ id: string; name: string; suggestions: number }>('/api/cvs/import', { filename, content_base64 }),
  approveCV: (id: string, approved: boolean) => post(`/api/cvs/${id}/approve`, { approved }),
  prepare: (id: string) => post<{ status: string; filled_count: number; unknown_count: number; blocking_count: number; source: string }>(`/api/applications/${id}/prepare`),
  liveFill: (id: string) => post(`/api/applications/${id}/live-fill`),
  validate: (id: string) => post<Validation>(`/api/applications/${id}/validate`),
  setStatus: (id: string, status: string) => post(`/api/applications/${id}/status`, { status }),
  deleteApplication: (id: string) => remove(`/api/applications/${id}`),
  answerQuestion: (body: Record<string, unknown>) => post<{ applications_updated: number; questions_remaining: number }>('/api/inbox/answer', body),
  draftAnswer: (question: string, job_id?: string) => post<Draft>('/api/inbox/draft-answer', { question, job_id }),
  acceptSuggestion: (id: string, value?: unknown) => post(`/api/suggestions/${id}/accept`, { value }),
  dismissSuggestion: (id: string) => post(`/api/suggestions/${id}/dismiss`),
  saveDraft: (id: string, content: string, approve: boolean) => post<{ ok: boolean; cv?: { id: string; name: string } }>(`/api/drafts/${id}`, { content, approve }),
  deleteDraft: (id: string) => remove(`/api/drafts/${id}`),
  follow: (url: string) => post<{ company: string; internships: number; total: number }>('/api/watchlist', { url }),
  unfollow: (id: string) => remove(`/api/watchlist/${id}`),
  runAutopilot: () => post<{ run_id: string }>('/api/autopilot/run'),
  readNotifications: () => post('/api/notifications/read'),
  aiStatus: () => request<AIStatus>('/api/ai/status'),
  pullModel: (model: string) => post('/api/ai/pull', { model }),
  emailSettings: (body: Record<string, unknown>) => post('/api/email/settings', body),
  emailSync: () => post<{ messages: number; moved: number }>('/api/email/sync'),
  emailEvents: () => request<EmailEvent[]>('/api/email/events'),
  undoEmail: (id: string) => post(`/api/email/events/${id}/undo`),
  backups: () => request<Backup[]>('/api/backups'),
  createBackup: () => post<Backup>('/api/backups', { label: 'manual' }),
  restoreBackup: (name: string) => post<{ safety_backup: Backup }>('/api/backups/restore', { name }),
  openBackups: () => post('/api/backups/open'),
  reset: (backup: boolean) => post<{ backup: Backup | null; browser_data_kept: boolean }>('/api/reset', { confirm: 'RESET', backup }),
  update: () => request<UpdateState>('/api/update'),
  checkUpdate: () => post<UpdateState>('/api/update/check'),
  downloadUpdate: () => post<UpdateState>('/api/update/download'),
  installUpdate: () => post<UpdateState>('/api/update/install'),
  postponeUpdate: () => post<UpdateState>('/api/update/postpone'),
  sources: () => request<{ sources: SourceInfo[]; worldwide: boolean }>('/api/sources'),
  githubRepos: (user: string) => request<GitHubRepo[]>(`/api/github/repos?user=${encodeURIComponent(user)}`),
  githubProject: (link: string) => post<GitHubProject>('/api/github/project', { link }),
  githubImport: (links: string[]) => post<{ saved: GitHubProject[]; errors: { link: string; error: string }[]; new_skills: string[] }>('/api/github/import', { links }),
}

export function readFileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(new Error('Could not read the file'))
    reader.readAsDataURL(file)
  })
}

export function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('Could not read the file'))
    reader.readAsText(file)
  })
}
