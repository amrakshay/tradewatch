import client from './client'

export const getLatestSignals = () =>
  client.get('/signals/latest').then(r => r.data)

export const getAlerts = (status) =>
  client.get('/alerts', { params: status ? { status } : {} }).then(r => r.data)

export const getSchedulerStatus = () =>
  client.get('/scheduler/status').then(r => r.data)
