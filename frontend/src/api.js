import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post('/auth/login/', { username, password })

export const logout = () => api.post('/auth/logout/')
export const getMe = () => api.get('/auth/me/')

// ── Sources ───────────────────────────────────────────────────────────────────
export const getSources = () => api.get('/sources/datasources/')
export const getJobs = () => api.get('/sources/jobs/')
export const getJob = (id) => api.get(`/sources/jobs/${id}/`)

// ── Ingestion ─────────────────────────────────────────────────────────────────
export const uploadFile = (file, sourceId, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  form.append('source_id', sourceId)
  return api.post('/ingestion/upload/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
  })
}

// ── Records ───────────────────────────────────────────────────────────────────
export const getRecords = (params = {}) => api.get('/records/', { params })
export const getRecord = (id) => api.get(`/records/${id}/`)
export const reviewRecord = (id, action, comment = '') =>
  api.post(`/records/${id}/review/`, { action, comment })

// ── Factors ───────────────────────────────────────────────────────────────────
export const getEmissionFactors = () => api.get('/factors/emission-factors/')
