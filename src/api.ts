import type { Analysis, Bootstrap, Fact, Job, Validation } from './types'

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
  saveFact: (fact: Fact) => post<Fact>('/api/profile/facts', fact),
  deleteFact: (id: string) => remove(`/api/profile/facts/${id}`),
  saveAnswer: (answer: Record<string, unknown>) => post<{ id: string; status: string }>('/api/answers', answer),
  approveAnswer: (id: string) => post(`/api/answers/${id}/approve`),
  deleteAnswer: (id: string) => remove(`/api/answers/${id}`),
  settings: (settings: Record<string, unknown>) => post('/api/settings', settings),
  importJob: (url: string) => post<Job>('/api/jobs/import', { url }),
  manualJob: (job: Record<string, unknown>) => post<Job>('/api/jobs/manual', job),
  deleteJob: (id: string) => remove(`/api/jobs/${id}`),
  importCV: (filename: string, content_base64: string) => post<{ id: string; name: string }>('/api/cvs/import', { filename, content_base64 }),
  approveCV: (id: string, approved: boolean) => post(`/api/cvs/${id}/approve`, { approved }),
  analyzeJob: (id: string) => post<Analysis>(`/api/jobs/${id}/analyze`),
  queueJob: (id: string) => post<{ id: string; status: string }>(`/api/jobs/${id}/queue`),
  dryRun: (id: string, fields: unknown[]) => post<{ status: string; filled_count: number; unknown_count: number }>(`/api/applications/${id}/dry-run`, { fields }),
  validate: (id: string) => post<Validation>(`/api/applications/${id}/validate`),
  setStatus: (id: string, status: string) => post(`/api/applications/${id}/status`, { status }),
  deleteApplication: (id: string) => remove(`/api/applications/${id}`),
}

export function readFileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(new Error('Could not read the file'))
    reader.readAsDataURL(file)
  })
}
