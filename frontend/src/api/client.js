import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    let msg
    if (Array.isArray(detail)) {
      // FastAPI 422 validation errors: [{loc, msg, type}, ...]
      msg = detail.map(e => {
        const field = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : null
        return field ? `${field}: ${e.msg}` : (e.msg || String(e))
      }).join('; ')
    } else {
      msg = detail || err.message || 'Unknown error'
    }
    console.error('API error:', msg)
    return Promise.reject(new Error(msg))
  }
)

export default client
