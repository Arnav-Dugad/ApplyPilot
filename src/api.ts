import type { AIStatus, AISummary, Analysis, Bootstrap, Draft, Fact, Job, JobDetail, Validation } from './types'

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
  summarize: (id: string) => post<AISummary>(`/api/jobs/${id}/summary`),
  coverLetter: (id: string) => post<Draft>(`/api/jobs/${id}/cover-letter`),
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
  saveDraft: (id: string, content: string, approve: boolean) => post(`/api/drafts/${id}`, { content, approve }),
  deleteDraft: (id: string) => remove(`/api/drafts/${id}`),
  follow: (url: string) => post<{ company: string; internships: number; total: number }>('/api/watchlist', { url }),
  unfollow: (id: string) => remove(`/api/watchlist/${id}`),
  runAutopilot: () => post<{ run_id: string }>('/api/autopilot/run'),
  readNotifications: () => post('/api/notifications/read'),
  aiStatus: () => request<AIStatus>('/api/ai/status'),
  pullModel: (model: string) => post('/api/ai/pull', { model }),
}

export function readFileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(new Error('Could not read the file'))
    reader.readAsDataURL(file)
  })
}
