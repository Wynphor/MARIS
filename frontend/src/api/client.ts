/**
 * HTTP 客户端 — 与 MathModel-Engine FastAPI 后端通信
 */
import axios from 'axios'

const BASE_URL = 'http://127.0.0.1:8000'
export { BASE_URL }

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Workspace ──
export const workspaceApi = {
  list: () => api.get('/api/v1/workspaces/'),
  create: (data: { title: string; question_id: string; problem_type: string }) =>
    api.post('/api/v1/workspaces/', data),
  tree: (id: string) => api.get(`/api/v1/workspaces/${id}/tree`),
  dashboard: (id: string) => api.get(`/api/v1/workspaces/${id}/dashboard`),
  getConfig: (id: string) => api.get(`/api/v1/workspaces/${id}/config`),
  updateConfig: (id: string, data: Record<string, any>) =>
    api.put(`/api/v1/workspaces/${id}/config`, data),
  upload: (id: string, formData: FormData) =>
    api.post(`/api/v1/workspaces/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  files: (id: string, subfolder = 'raw') =>
    api.get(`/api/v1/workspaces/${id}/files`, { params: { subfolder } }),
  dataPreview: (id: string, file = '') =>
    api.get(`/api/v1/workspaces/${id}/data/preview`, { params: { file } }),
  downloadPdf: (id: string) => `${BASE_URL}/api/v1/workspaces/${id}/download/pdf`,
  previewPdf: (id: string) => `${BASE_URL}/api/v1/workspaces/${id}/preview/pdf`,
  downloadZip: (id: string) => `${BASE_URL}/api/v1/workspaces/${id}/download/zip`,
  triage: (data: Record<string, any>) => api.post('/api/v1/workspaces/triage', data),
}

// ── Pipeline ──
export const pipelineApi = {
  execute: (data: Record<string, any>) => api.post('/api/v1/pipeline/execute', data),
  stages: () => api.get('/api/v1/pipeline/stages'),
  approve: (id: string) => api.post(`/api/v1/pipeline/${id}/approve`),
  reject: (id: string, feedback = '') => api.post(`/api/v1/pipeline/${id}/reject`, { feedback }),
}

// ── Editor ──
export const editorApi = {
  readFile: (wsId: string, path: string) => api.get(`/api/v1/editor/files/${wsId}/${path}`),
  saveFile: (wsId: string, path: string, content: string) =>
    api.put(`/api/v1/editor/files/${wsId}/${path}`, { content }),
  diff: (wsId: string, path: string) => api.get(`/api/v1/editor/diff/${wsId}/${path}`),
  aiEdit: (wsId: string, path: string, instruction: string) =>
    api.post(`/api/v1/editor/ai-edit/${wsId}/${path}`, { instruction }),
  compile: (wsId: string) => api.post(`/api/v1/editor/compile/${wsId}`),
  runCode: (wsId: string, script = 'solve_all.py') =>
    api.post(`/api/v1/editor/run/${wsId}`, null, { params: { script } }),
}

// ── Tasks ──
export const taskApi = {
  get: (id: string) => api.get(`/api/v1/tasks/${id}`),
  list: (wsId: string, limit = 50) => api.get(`/api/v1/tasks/workspace/${wsId}`, { params: { limit } }),
  events: (id: string) => api.get(`/api/v1/tasks/${id}/events`),
}

// ── Health ──
export const healthApi = {
  check: () => api.get('/health'),
  ready: () => api.get('/ready'),
}

// ── System Config ──
export const systemApi = {
  getConfig: () => api.get('/api/v1/system/config'),
  updateConfig: (data: { default_model?: string; data_dir?: string }) =>
    api.put('/api/v1/system/config', data),
  updateProvider: (providerId: string, data: { api_key?: string; base_url?: string }) =>
    api.put(`/api/v1/system/config/providers/${providerId}`, data),
}

export default api
