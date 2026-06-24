# T20 — Backtest Page

| Field | Value |
|-------|-------|
| Phase | 3 |
| Depends on | T13, T16 |
| Unlocks | T22 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the Backtest page: stock selector, date range with quick presets, threshold + days inputs, results summary, qualifying days table, and a Recharts bar chart of return % over time.

## Files to Create / Modify

- `frontend/src/pages/Backtest.jsx` (replace placeholder)
- `frontend/src/api/backtest.js`
- `frontend/src/components/backtest/BacktestForm.jsx`
- `frontend/src/components/backtest/BacktestResults.jsx`

## Steps

### 1. `frontend/src/api/backtest.js`

```js
import client from './client'

export const runBacktest = (data) =>
  client.post('/backtest', data).then(r => r.data)
```

### 2. Date preset helpers

```js
// utils/dates.js
export function getPresetRange(preset) {
  const today = new Date()
  const fmt = (d) => d.toISOString().slice(0, 10)

  const offsets = {
    '3m':  90,
    '6m':  180,
    '1y':  365,
    '2y':  730,
  }
  const days = offsets[preset]
  if (!days) return null

  const from = new Date(today)
  from.setDate(from.getDate() - days)
  return { from_date: fmt(from), to_date: fmt(today) }
}
```

### 3. `frontend/src/components/backtest/BacktestForm.jsx`

```jsx
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
      {/* Stock selector */}
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

      {/* Date presets */}
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

      {/* Parameters */}
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
```

### 4. `frontend/src/components/backtest/BacktestResults.jsx`

```jsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function BacktestResults({ result }) {
  const { symbol, from_date, to_date, total_trading_days, qualifying_days,
          pct_threshold, num_days, results } = result

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Trading Days', value: total_trading_days },
          { label: 'Qualifying Days', value: qualifying_days },
          { label: 'Hit Rate', value: `${((qualifying_days / total_trading_days) * 100).toFixed(1)}%` },
          { label: 'Threshold', value: `${pct_threshold}% / ${num_days}d` },
        ].map(c => (
          <div key={c.label} className="bg-white border border-gray-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">{c.value}</div>
            <div className="text-xs text-gray-500 mt-1">{c.label}</div>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      {results.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="text-sm font-medium mb-4">Return % on Qualifying Days — {symbol}</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={results} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip
                formatter={(v) => [`${v.toFixed(2)}%`, 'Return']}
                labelFormatter={(d) => `Date: ${d}`}
              />
              <ReferenceLine y={pct_threshold} stroke="#94a3b8" strokeDasharray="4 2"
                label={{ value: `${pct_threshold}%`, position: 'right', fontSize: 11 }} />
              <Bar dataKey="return_pct" fill="#3b82f6" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Qualifying days table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              {['Date','Close Price','Start Price','Return %'].map(h => (
                <th key={h} className="text-left px-4 py-3 font-medium text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-gray-400">No qualifying days in this range.</td></tr>
            )}
            {results.map(r => (
              <tr key={r.date} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3">{r.date}</td>
                <td className="px-4 py-3">₹{r.close_price.toLocaleString('en-IN',{minimumFractionDigits:2})}</td>
                <td className="px-4 py-3 text-gray-500">₹{r.start_price.toLocaleString('en-IN',{minimumFractionDigits:2})}</td>
                <td className="px-4 py-3 text-green-600 font-medium">+{r.return_pct.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

### 5. `frontend/src/pages/Backtest.jsx`

```jsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runBacktest } from '../api/backtest'
import BacktestForm from '../components/backtest/BacktestForm'
import BacktestResults from '../components/backtest/BacktestResults'

export default function Backtest() {
  const [result, setResult] = useState(null)

  const mutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: setResult,
  })

  return (
    <div className="max-w-3xl space-y-6">
      <BacktestForm
        onSubmit={mutation.mutate}
        loading={mutation.isPending}
      />

      {mutation.isError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">
          {mutation.error.message}
        </div>
      )}

      {result && <BacktestResults result={result} />}
    </div>
  )
}
```

## Done When
- `/backtest` renders form with stock dropdown populated from `/api/stocks`
- Date preset buttons auto-fill from/to dates
- Submitting triggers `POST /api/backtest` and displays results
- Summary cards show total_trading_days, qualifying_days, hit rate
- Bar chart renders one bar per qualifying day with correct return % values
- Reference line at pct_threshold (default 10%)
- Table lists qualifying dates with close/start prices and return %
- Running the same backtest twice is fast on second run (candle cache hit)
