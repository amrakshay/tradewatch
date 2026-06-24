import client from './client'

export const runBacktest = (data) =>
  client.post('/backtest', data).then(r => r.data)
