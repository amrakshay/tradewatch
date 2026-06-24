import client from './client'

export const getConfig = () => client.get('/config').then(r => r.data)
export const updateConfig = (data) => client.put('/config', data).then(r => r.data)
export const testDhanConnection = () => client.post('/config/test-dhan').then(r => r.data)
export const renewDhanToken = () => client.post('/config/renew-token').then(r => r.data)
export const testTelegram = () => client.post('/config/test-telegram').then(r => r.data)
