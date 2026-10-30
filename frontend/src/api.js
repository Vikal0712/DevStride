import axios from 'axios'
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000', withCredentials: true, headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' } })
api.interceptors.response.use(r => r, e => Promise.reject(new Error(e.response?.data?.detail || e.message || 'Something went wrong')))
