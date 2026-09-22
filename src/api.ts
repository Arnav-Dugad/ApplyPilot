import type { Bootstrap, Fact } from './types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`)
  return body as T
}

export const api = {
  bootstrap: () => request<Bootstrap>('/api/bootstrap'),
  saveFact: (fact: Fact) => request<Fact>('/api/profile/facts', { method: 'POST', body: JSON.stringify(fact) }),
  saveAnswer: (answer: Record<string, unknown>) => request('/api/answers', { method: 'POST', body: JSON.stringify(answer) }),
  settings: (settings: Record<string, unknown>) => request('/api/settings', { method: 'POST', body: JSON.stringify(settings) }),
  importJob: (url: string) => request('/api/jobs/import', { method: 'POST', body: JSON.stringify({ url }) }),
  importCV: (filename: string, content_base64: string) => request('/api/cvs/import', { method: 'POST', body: JSON.stringify({ filename, content_base64 }) }),
  manualJob: (job: Record<string, unknown>) => request('/api/jobs/manual', { method: 'POST', body: JSON.stringify(job) }),
  analyzeJob: (id: string) => request<{ result: string; checks: { name: string; result: string; explanation: string }[]; match: { strong: string[]; partial: string[]; missing: string[] } }>(`/api/jobs/${id}/analyze`, { method: 'POST', body: '{}' }),
  queueJob: (id: string) => request<{ id: string; status: string }>(`/api/jobs/${id}/queue`, { method: 'POST', body: '{}' }),
  dryRun: (id: string, fields: unknown[]) => request<{ status: string; fields: unknown[]; filled_count: number; unknown_count: number }>(`/api/applications/${id}/dry-run`, { method: 'POST', body: JSON.stringify({ fields }) }),
  validate: (id: string) => request<{ valid: boolean; blocked: boolean; failures: string[]; warnings: string[] }>(`/api/applications/${id}/validate`, { method: 'POST', body: '{}' }),
}
