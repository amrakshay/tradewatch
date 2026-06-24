import client from './client'

export const getAlerts = (status) =>
  client.get('/alerts', { params: status ? { status } : {} }).then(r => r.data)

export const createAlert = (data) =>
  client.post('/alerts', data).then(r => r.data)

export const updateAlert = (id, data) =>
  client.patch(`/alerts/${id}`, data).then(r => r.data)

export const deleteAlert = (id) =>
  client.delete(`/alerts/${id}`).then(r => r.data)

export const getAlertHistory = (id) =>
  client.get(`/alerts/${id}/history`).then(r => r.data)

export const getAllHistory = () =>
  client.get('/alerts/history/all').then(r => r.data)
