import client from './client'

export const getSignalDates = () =>
  client.get('/signals/dates').then(r => r.data)

export const getSignals = (date) =>
  client.get('/signals', { params: { date } }).then(r => r.data)

export const getLatestSignals = () =>
  client.get('/signals/latest').then(r => r.data)

export const runScanner = () =>
  client.post('/scanner/run').then(r => r.data)

export const getScannerProgress = () =>
  client.get('/scanner/progress').then(r => r.data)
