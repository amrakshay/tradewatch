import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getStocks } from '../../api/stocks'
import { getPresetRange } from '../../utils/dates'

const PRESETS = [
  { label: '3 months', value: '3m' },
  { label: '6 months', value: '6m' },
  { label: '1 year',   value: '1y' },
  { label: '2 years',  value: '2y' },
]

export default function BacktestForm({ onSubmit, loading }) {
  const { data: stocks = [] } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => getStocks(true),
  })

  const [securityId, setSecurityId] = useState('')
  const [symbol, setSymbol] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [preset, setPreset] = useState('')
  const [pct, setPct] = useState(10)
  const [days, setDays] = useState(4)

  const handlePreset = (p) => {
    setPreset(p)
    const range = getPresetRange(p)
    if (range) { setFromDate(range.from_date); setToDate(range.to_date) }
  }

  const handleStockChange = (e) => {
    const sid = e.target.value
    setSecurityId(sid)
    const s = stocks.find(s => s.security_id === sid)
    if (s) setSymbol(s.symbol)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!securityId || !fromDate || !toDate) return
    onSubmit({ symbol, security_id: securityId, from_date: fromDate,
               to_date: toDate, pct_threshold: pct, num_days: days })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded-lg p-6 space-y-5">
      <div>
        <label className="block text-sm font-medium mb-1">Stock</label>
        <select
          value={securityId}
          onChange={handleStockChange}
          required
          className="w-full border rounded px-3 py-2 text-sm"
        >
          <option value="">— select a stock —</option>
          {stocks.map(s => (
            <option key={s.security_id} value={s.security_id}>
              {s.symbol} — {s.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Date Range</label>
        <div className="flex gap-2 mb-2 flex-wrap">
          {PRESETS.map(p => (
            <button
              key={p.value}
              type="button"
              onClick={() => handlePreset(p.value)}
              className={`px-3 py-1 text-xs rounded border transition-colors ${
                preset === p.value
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'border-gray-300 hover:border-blue-400'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-xs text-gray-500">From</label>
            <input type="date" value={fromDate} onChange={e => { setFromDate(e.target.value); setPreset('') }}
              required className="w-full border rounded px-3 py-2 text-sm" />
          </div>
          <div className="flex-1">
            <label className="text-xs text-gray-500">To</label>
            <input type="date" value={toDate} onChange={e => { setToDate(e.target.value); setPreset('') }}
              required className="w-full border rounded px-3 py-2 text-sm" />
          </div>
        </div>
      </div>

      <div className="flex gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Return Threshold (%)</label>
          <input type="number" step="0.5" min="1" value={pct}
            onChange={e => setPct(parseFloat(e.target.value))}
            className="w-full border rounded px-3 py-2 text-sm" />
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Trading Days</label>
          <input type="number" min="1" max="30" value={days}
            onChange={e => setDays(parseInt(e.target.value))}
            className="w-full border rounded px-3 py-2 text-sm" />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || !securityId || !fromDate || !toDate}
        className="w-full py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Running…' : 'Run Backtest'}
      </button>
    </form>
  )
}
