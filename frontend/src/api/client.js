import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    console.error('API error:', msg)
    return Promise.reject(new Error(msg))
  }
)

export default client
