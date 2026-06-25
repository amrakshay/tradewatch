import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getConfig, updateConfig, testDhanConnection, renewDhanToken, testTelegram,
} from '../api/config'
import {
  getStocks, addStock, toggleStock, deleteStock, syncNifty500, resetStockStatus,
} from '../api/stocks'

// ─── Toast ───────────────────────────────────────────────────────────────────

function useToast() {
  const [toasts, setToasts] = useState([])

  const toast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500)
  }, [])

  return { toasts, toast }
}

function ToastContainer({ toasts }) {
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-6 right-6 space-y-2 z-50">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white font-medium transition-all ${
            t.type === 'error' ? 'bg-red-600' : 'bg-green-600'
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}

// ─── Shared UI ───────────────────────────────────────────────────────────────

function Card({ children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 shadow-sm ${className}`}>
      {children}
    </div>
  )
}

function CardHeader({ children }) {
  return <div className="px-6 py-4 border-b border-gray-100">{children}</div>
}

function CardTitle({ children }) {
  return <h2 className="text-base font-semibold text-gray-900">{children}</h2>
}

function CardContent({ children }) {
  return <div className="px-6 py-5">{children}</div>
}

function Label({ children }) {
  return <label className="block text-sm font-medium text-gray-700 mb-1">{children}</label>
}

function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${className}`}
      {...props}
    />
  )
}

function Button({ children, variant = 'primary', size = 'sm', disabled, onClick, className = '' }) {
  const base = 'inline-flex items-center justify-center rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
  const sizes = { sm: 'px-3 py-2', md: 'px-4 py-2' }
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700',
    outline: 'border border-gray-300 text-gray-700 hover:bg-gray-50',
    danger: 'text-red-600 hover:underline',
    ghost: 'text-gray-500 hover:underline',
  }
  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function StatusBadge({ status }) {
  const map = {
    active: 'bg-green-100 text-green-800',
    expiring_soon: 'bg-yellow-100 text-yellow-800',
    expired: 'bg-red-100 text-red-800',
    error: 'bg-red-100 text-red-800',
    unknown: 'bg-gray-100 text-gray-600',
  }
  const labels = {
    active: 'Valid',
    expiring_soon: 'Expiring Soon',
    expired: 'Expired',
    error: 'Error',
    unknown: 'Not Set',
  }
  const cls = map[status] || map.unknown
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {labels[status] || status}
    </span>
  )
}

// ─── Token Field ──────────────────────────────────────────────────────────────

function TokenField({ label, maskedValue, fieldName, onSave }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')

  if (!editing) {
    return (
      <div className="flex items-center gap-2">
        <input
          type="password"
          value={maskedValue || '(not set)'}
          disabled
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500"
          readOnly
        />
        <button
          onClick={() => setEditing(true)}
          className="text-sm text-blue-600 hover:underline whitespace-nowrap"
        >
          Change
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="password"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder={`Enter new ${label}`}
        className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        autoFocus
      />
      <button
        onClick={() => {
          if (value) onSave(fieldName, value)
          setEditing(false)
          setValue('')
        }}
        className="text-sm text-green-700 font-medium hover:underline whitespace-nowrap"
      >
        Save
      </button>
      <button
        onClick={() => { setEditing(false); setValue('') }}
        className="text-sm text-gray-500 hover:underline whitespace-nowrap"
      >
        Cancel
      </button>
    </div>
  )
}

// ─── Scanner Settings Card ────────────────────────────────────────────────────

function ScannerSettingsCard({ config, toast }) {
  const qc = useQueryClient()
  const [scanTime, setScanTime] = useState(config.scan_time)
  const [pct, setPct] = useState(config.scan_percentage)
  const [days, setDays] = useState(config.scan_days)
  const [alertInterval, setAlertInterval] = useState(config.alert_check_interval_mins)
  const [alertStart, setAlertStart] = useState(config.alert_check_start)
  const [alertEnd, setAlertEnd] = useState(config.alert_check_end)

  const mutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      qc.invalidateQueries(['config'])
      toast('Scanner settings saved')
    },
    onError: err => toast(err.message, 'error'),
  })

  const save = () => mutation.mutate({
    scan_time: scanTime,
    scan_percentage: parseFloat(pct),
    scan_days: parseInt(days),
    alert_check_interval_mins: parseInt(alertInterval),
    alert_check_start: alertStart,
    alert_check_end: alertEnd,
  })

  return (
    <Card>
      <CardHeader><CardTitle>Scanner Settings</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Scan Time (IST)</Label>
            <Input type="time" value={scanTime} onChange={e => setScanTime(e.target.value)} />
          </div>
          <div>
            <Label>Return Threshold (%)</Label>
            <Input
              type="number"
              step="0.5"
              min="1"
              value={pct}
              onChange={e => setPct(e.target.value)}
            />
          </div>
          <div>
            <Label>Trading Days</Label>
            <Input
              type="number"
              min="1"
              max="30"
              value={days}
              onChange={e => setDays(e.target.value)}
            />
          </div>
          <div>
            <Label>Alert Interval (mins)</Label>
            <Input
              type="number"
              min="1"
              max="60"
              value={alertInterval}
              onChange={e => setAlertInterval(e.target.value)}
            />
          </div>
          <div>
            <Label>Alert Window Start (IST)</Label>
            <Input type="time" value={alertStart} onChange={e => setAlertStart(e.target.value)} />
          </div>
          <div>
            <Label>Alert Window End (IST)</Label>
            <Input type="time" value={alertEnd} onChange={e => setAlertEnd(e.target.value)} />
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={save} disabled={mutation.isPending} size="md">
            {mutation.isPending ? 'Saving…' : 'Save Settings'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Dhan API Card ────────────────────────────────────────────────────────────

function DhanApiCard({ config, toast }) {
  const qc = useQueryClient()
  const [clientId, setClientId] = useState(config.dhan_client_id)
  const [testResult, setTestResult] = useState(null)

  const saveMutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      qc.invalidateQueries(['config'])
      toast('Dhan API settings saved')
    },
    onError: err => toast(err.message, 'error'),
  })

  const testMutation = useMutation({
    mutationFn: testDhanConnection,
    onSuccess: data => {
      setTestResult(data)
      qc.invalidateQueries(['config'])
    },
    onError: err => toast(err.message, 'error'),
  })

  const renewMutation = useMutation({
    mutationFn: renewDhanToken,
    onSuccess: data => {
      if (data.success) {
        toast(`Token renewed. Expires: ${data.new_expires_at || 'unknown'}`)
        qc.invalidateQueries(['config'])
      } else {
        toast(data.message, 'error')
      }
    },
    onError: err => toast(err.message, 'error'),
  })

  const handleTokenSave = (field, value) => {
    saveMutation.mutate({ [field]: value })
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Dhan API</CardTitle>
          <StatusBadge status={config.token_status} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <Label>Client ID</Label>
            <div className="flex gap-2">
              <Input
                value={clientId}
                onChange={e => setClientId(e.target.value)}
              />
              <Button
                onClick={() => saveMutation.mutate({ dhan_client_id: clientId })}
                disabled={saveMutation.isPending}
                variant="outline"
              >
                Save
              </Button>
            </div>
          </div>

          <div>
            <Label>Access Token</Label>
            <TokenField
              label="access token"
              maskedValue={config.dhan_access_token_masked}
              fieldName="dhan_access_token"
              onSave={(field, value) => handleTokenSave(field, value)}
            />
          </div>

          {config.token_expires_at && (
            <p className="text-xs text-gray-500">
              Token expires: {new Date(config.token_expires_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
            </p>
          )}

          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={() => { setTestResult(null); testMutation.mutate() }}
              disabled={testMutation.isPending}
              variant="outline"
            >
              {testMutation.isPending ? 'Testing…' : 'Test Connection'}
            </Button>
            <Button
              onClick={() => renewMutation.mutate()}
              disabled={renewMutation.isPending}
              variant="outline"
            >
              {renewMutation.isPending ? 'Renewing…' : 'Renew Token'}
            </Button>
          </div>

          {testResult && (
            <div className={`text-sm px-3 py-2 rounded-lg ${testResult.valid ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
              {testResult.message}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Telegram Card ────────────────────────────────────────────────────────────

function TelegramCard({ config, toast }) {
  const qc = useQueryClient()
  const [chatId, setChatId] = useState(config.telegram_chat_id)
  const [testResult, setTestResult] = useState(null)

  const saveMutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      qc.invalidateQueries(['config'])
      toast('Telegram settings saved')
    },
    onError: err => toast(err.message, 'error'),
  })

  const testMutation = useMutation({
    mutationFn: testTelegram,
    onSuccess: data => {
      setTestResult(data.sent)
      if (data.sent) {
        toast('Test message sent successfully')
      } else {
        toast('Failed to send test message — check credentials', 'error')
      }
    },
    onError: err => {
      setTestResult(false)
      toast(err.message, 'error')
    },
  })

  return (
    <Card>
      <CardHeader><CardTitle>Telegram Notifications</CardTitle></CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <Label>Bot Token</Label>
            <TokenField
              label="bot token"
              maskedValue={config.telegram_bot_token_masked}
              fieldName="telegram_bot_token"
              onSave={(field, value) => saveMutation.mutate({ [field]: value })}
            />
          </div>

          <div>
            <Label>Chat ID</Label>
            <div className="flex gap-2">
              <Input
                value={chatId}
                onChange={e => setChatId(e.target.value)}
                placeholder="e.g. -100123456789"
              />
              <Button
                onClick={() => saveMutation.mutate({ telegram_chat_id: chatId })}
                disabled={saveMutation.isPending}
                variant="outline"
              >
                Save
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={() => { setTestResult(null); testMutation.mutate() }}
              disabled={testMutation.isPending}
              variant="outline"
            >
              {testMutation.isPending ? 'Sending…' : 'Send Test Message'}
            </Button>
            {testResult !== null && (
              <span className={`text-sm font-medium ${testResult ? 'text-green-700' : 'text-red-700'}`}>
                {testResult ? 'Sent!' : 'Failed'}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Add Stock Modal ──────────────────────────────────────────────────────────

function AddStockModal({ onClose, onAdd }) {
  const [form, setForm] = useState({
    symbol: '',
    security_id: '',
    name: '',
    exchange_segment: 'NSE_EQ',
    universe_tag: 'CUSTOM',
  })
  const [saving, setSaving] = useState(false)

  const set = field => e => setForm(prev => ({ ...prev, [field]: e.target.value }))

  const handleSubmit = async e => {
    e.preventDefault()
    setSaving(true)
    try {
      await onAdd(form)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 className="text-base font-semibold text-gray-900 mb-4">Add Custom Stock</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <Label>Symbol *</Label>
            <Input value={form.symbol} onChange={set('symbol')} required placeholder="e.g. RELIANCE" />
          </div>
          <div>
            <Label>Security ID *</Label>
            <Input value={form.security_id} onChange={set('security_id')} required placeholder="Dhan security_id" />
          </div>
          <div>
            <Label>Name</Label>
            <Input value={form.name} onChange={set('name')} placeholder="Company name" />
          </div>
          <div>
            <Label>Exchange Segment</Label>
            <select
              value={form.exchange_segment}
              onChange={set('exchange_segment')}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="NSE_EQ">NSE_EQ</option>
              <option value="BSE_EQ">BSE_EQ</option>
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving} size="md">
              {saving ? 'Adding…' : 'Add Stock'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Stock Universe Card ──────────────────────────────────────────────────────

function StockUniverseCard({ toast }) {
  const qc = useQueryClient()
  const [syncing, setSyncing] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [filter, setFilter] = useState('all') // 'all' | 'no_data'
  const [syncResult, setSyncResult] = useState(null)

  const { data: stocks = [], isLoading } = useQuery({
    queryKey: ['stocks-all'],
    queryFn: () => getStocks(false),
  })

  const noDataCount = stocks.filter(s => s.data_status === 'no_data').length

  const visible = filter === 'no_data'
    ? stocks.filter(s => s.data_status === 'no_data')
    : stocks

  const handleSync = async () => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const result = await syncNifty500()
      setSyncResult(result)
      qc.invalidateQueries(['stocks-all'])
      if (result.no_data_count > 0) {
        toast(`Sync done — ${result.no_data_count} stock(s) flagged with no data`, 'error')
      } else {
        toast(`Synced: ${result.matched} matched, ${result.unmatched} unmatched, ${result.validated} validated`)
      }
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSyncing(false)
    }
  }

  const handleToggle = async (id, is_active) => {
    try {
      await toggleStock(id, is_active)
      qc.invalidateQueries(['stocks-all'])
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const handleReset = async (id, symbol) => {
    try {
      await resetStockStatus(id)
      qc.invalidateQueries(['stocks-all'])
      toast(`${symbol} re-enabled for scanning`)
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const handleDelete = async id => {
    if (!confirm('Remove this stock?')) return
    try {
      await deleteStock(id)
      qc.invalidateQueries(['stocks-all'])
      toast('Stock removed')
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const handleAdd = async formData => {
    try {
      const stock = await addStock(formData)
      qc.invalidateQueries(['stocks-all'])
      if (stock.data_status === 'no_data') {
        toast(`${formData.symbol} added but flagged: ${stock.data_error}`, 'error')
      } else {
        toast(`${formData.symbol} added and validated`)
      }
    } catch (err) {
      toast(err.message, 'error')
      throw err
    }
  }

  return (
    <>
      {showAdd && <AddStockModal onClose={() => setShowAdd(false)} onAdd={handleAdd} />}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CardTitle>Stock Universe</CardTitle>
              {noDataCount > 0 && (
                <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
                  {noDataCount} no-data
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowAdd(true)}>Add Custom Stock</Button>
              <Button variant="outline" onClick={handleSync} disabled={syncing}>
                {syncing ? 'Syncing…' : 'Sync Nifty 500'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-gray-500">Loading stocks…</p>
          ) : stocks.length === 0 ? (
            <p className="text-sm text-gray-500">No stocks in universe. Sync Nifty 500 to populate.</p>
          ) : (
            <>
              {syncResult && (
                <div className={`mb-4 rounded-lg border p-4 text-sm space-y-2 ${
                  syncResult.no_data_count > 0
                    ? 'border-amber-200 bg-amber-50'
                    : 'border-green-200 bg-green-50'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-800">Last sync result</span>
                    <button onClick={() => setSyncResult(null)} className="text-gray-400 hover:text-gray-600 text-xs">Dismiss</button>
                  </div>
                  <div className="flex gap-4 text-xs text-gray-600">
                    <span>{syncResult.matched} matched</span>
                    <span>{syncResult.unmatched} unmatched</span>
                    <span>{syncResult.validated} validated</span>
                    {syncResult.no_data_count > 0 && (
                      <span className="text-amber-700 font-medium">{syncResult.no_data_count} flagged no-data</span>
                    )}
                  </div>
                  {syncResult.unmatched_symbols?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-700 mb-1">No Dhan ticker match:</p>
                      <p className="text-xs text-gray-500 font-mono">{syncResult.unmatched_symbols.join(', ')}</p>
                    </div>
                  )}
                  {syncResult.no_data_symbols?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-amber-700 mb-1">Flagged (no data / &lt;4 trading days):</p>
                      <p className="text-xs text-amber-600 font-mono">{syncResult.no_data_symbols.join(', ')}</p>
                    </div>
                  )}
                </div>
              )}
              <div className="flex items-center gap-2 mb-3">
                <button
                  onClick={() => setFilter('all')}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    filter === 'all'
                      ? 'bg-gray-900 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  All ({stocks.length})
                </button>
                <button
                  onClick={() => setFilter('no_data')}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    filter === 'no_data'
                      ? 'bg-amber-600 text-white'
                      : 'bg-amber-50 text-amber-700 hover:bg-amber-100'
                  }`}
                >
                  No Data ({noDataCount})
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wider">
                      <th className="py-2 pr-4 font-medium">Symbol</th>
                      <th className="py-2 pr-4 font-medium">Name</th>
                      <th className="py-2 pr-4 font-medium">Universe</th>
                      <th className="py-2 pr-4 font-medium">Status</th>
                      <th className="py-2 pr-4 font-medium text-center">Active</th>
                      <th className="py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map(s => (
                      <tr
                        key={s.id}
                        className={`border-b border-gray-100 last:border-0 hover:bg-gray-50 ${
                          s.data_status === 'no_data' ? 'bg-amber-50/40' : ''
                        }`}
                      >
                        <td className="py-2 pr-4 font-mono font-medium text-gray-900">{s.symbol}</td>
                        <td className="py-2 pr-4 text-gray-600 max-w-xs truncate">{s.name}</td>
                        <td className="py-2 pr-4">
                          <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                            {s.universe_tag}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          {s.data_status === 'no_data' ? (
                            <span
                              title={s.data_error || 'No historical data from Dhan'}
                              className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-medium cursor-help"
                            >
                              No Data
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                        <td className="py-2 pr-4 text-center">
                          <input
                            type="checkbox"
                            checked={s.is_active}
                            onChange={e => handleToggle(s.id, e.target.checked)}
                            className="w-4 h-4 rounded border-gray-300 text-blue-600 cursor-pointer"
                          />
                        </td>
                        <td className="py-2">
                          <div className="flex items-center gap-3">
                            {s.data_status === 'no_data' && (
                              <button
                                onClick={() => handleReset(s.id, s.symbol)}
                                className="text-amber-600 hover:underline text-xs"
                              >
                                Re-enable
                              </button>
                            )}
                            <button
                              onClick={() => handleDelete(s.id)}
                              className="text-red-500 hover:underline text-xs"
                            >
                              Remove
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-gray-400 mt-3">{visible.length} of {stocks.length} stock{stocks.length !== 1 ? 's' : ''}</p>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </>
  )
}

// ─── Settings Page ────────────────────────────────────────────────────────────

export default function Settings() {
  const { toasts, toast } = useToast()

  const { data: config, isLoading, isError, error } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500 text-sm">
        Loading settings…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-48 text-red-600 text-sm">
        Failed to load settings: {error.message}
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">Configure scanner, API credentials, and stock universe.</p>
      </div>

      <ScannerSettingsCard config={config} toast={toast} />
      <DhanApiCard config={config} toast={toast} />
      <TelegramCard config={config} toast={toast} />
      <StockUniverseCard toast={toast} />

      <ToastContainer toasts={toasts} />
    </div>
  )
}
