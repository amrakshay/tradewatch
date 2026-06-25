import client from './client'

export const getStocks = (activeOnly = true) =>
  client.get('/stocks', { params: { active: activeOnly } }).then(r => r.data)
export const addStock = (data) => client.post('/stocks', data).then(r => r.data)
export const toggleStock = (id, is_active) =>
  client.patch(`/stocks/${id}`, null, { params: { is_active } }).then(r => r.data)
export const deleteStock = (id) => client.delete(`/stocks/${id}`).then(r => r.data)
export const syncNifty500 = () => client.post('/stocks/sync-nifty500').then(r => r.data)
export const resetStockStatus = (id) => client.post(`/stocks/${id}/reset-status`).then(r => r.data)
