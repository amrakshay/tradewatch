# T18 — Signals Page

| Field | Value |
|-------|-------|
| Phase | 3 |
| Depends on | T10, T16 |
| Unlocks | T21, T22 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the Signals page: date picker defaulting to latest scan date, signals table with return % and alert badge, "Set Alert" modal, and a "Run Scanner Now" button.

## Files to Create / Modify

- `frontend/src/pages/Signals.jsx` (replace placeholder)
- `frontend/src/api/signals.js`
- `frontend/src/components/signals/SignalTable.jsx`
- `frontend/src/components/signals/SetAlertModal.jsx`

## Steps

### 1. `frontend/src/api/signals.js`

```js
import client from './client'

export const getSignalDates = () =>
  client.get('/signals/dates').then(r => r.data)

export const getSignals = (date) =>
  client.get('/signals', { params: { date } }).then(r => r.data)

export const getLatestSignals = () =>
  client.get('/signals/latest').then(r => r.data)

export const runScanner = () =>
  client.post('/scanner/run').then(r => r.data)
```

### 2. `frontend/src/pages/Signals.jsx`

```jsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSignalDates, getSignals, runScanner } from '../api/signals'
import SignalTable from '../components/signals/SignalTable'
import SetAlertModal from '../components/signals/SetAlertModal'

export default function Signals() {
  const qc = useQueryClient()
  const [selectedDate, setSelectedDate] = useState(null)
  const [alertTarget, setAlertTarget] = useState(null)  // signal row for modal

  // Fetch available dates
  const { data: dates = [] } = useQuery({
    queryKey: ['signal-dates'],
    queryFn: getSignalDates,
    onSuccess: (d) => { if (!selectedDate && d.length > 0) setSelectedDate(d[0]) },
  })

  // Fetch signals for selected date
  const { data: signalsData, isLoading } = useQuery({
    queryKey: ['signals', selectedDate],
    queryFn: () => getSignals(selectedDate),
    enabled: !!selectedDate,
  })

  // Manual scan trigger
  const scanMutation = useMutation({
    mutationFn: runScanner,
    onSuccess: (result) => {
      alert(`Scan complete: ${result.qualified} signals found on ${result.scan_date}`)
      qc.invalidateQueries(['signal-dates'])
      qc.invalidateQueries(['signals'])
    },
  })

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-700">Date</label>
          <select
            value={selectedDate || ''}
            onChange={e => setSelectedDate(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm"
          >
            {dates.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
          {signalsData && (
            <span className="text-sm text-gray-500">
              {signalsData.count} signal{signalsData.count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <button
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {scanMutation.isPending ? 'Scanning…' : 'Run Scanner Now'}
        </button>
      </div>

      {/* Signals table */}
      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : (
        <SignalTable
          signals={signalsData?.signals || []}
          onSetAlert={setAlertTarget}
        />
      )}

      {/* Alert modal */}
      {alertTarget && (
        <SetAlertModal
          signal={alertTarget}
          onClose={() => setAlertTarget(null)}
          onCreated={() => {
            setAlertTarget(null)
            qc.invalidateQueries(['signals', selectedDate])  // refresh has_alert badges
          }}
        />
      )}
    </div>
  )
}
```

### 3. `frontend/src/components/signals/SignalTable.jsx`

```jsx
export default function SignalTable({ signals, onSetAlert }) {
  if (!signals.length) {
    return <p className="text-gray-400 text-sm">No signals for this date.</p>
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Symbol</th>
            <th className="text-right px-4 py-3 font-medium text-gray-600">Return %</th>
            <th className="text-right px-4 py-3 font-medium text-gray-600">Close</th>
            <th className="text-right px-4 py-3 font-medium text-gray-600">Start Price</th>
            <th className="text-right px-4 py-3 font-medium text-gray-600">Days</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {signals.map(s => (
            <tr key={s.id} className="border-b last:border-0 hover:bg-gray-50">
              <td className="px-4 py-3 font-mono font-medium">
                {s.symbol}
                {s.has_alert && (
                  <span className="ml-2 text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded">
                    Alert set
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-right text-green-600 font-semibold">
                +{s.return_pct.toFixed(2)}%
              </td>
              <td className="px-4 py-3 text-right">₹{s.close_price.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
              <td className="px-4 py-3 text-right text-gray-500">₹{s.start_price.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
              <td className="px-4 py-3 text-right text-gray-500">{s.scan_days}d</td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onSetAlert(s)}
                  className="text-blue-600 hover:underline text-xs"
                >
                  Set Alert
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

### 4. `frontend/src/components/signals/SetAlertModal.jsx`

```jsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import client from '../../api/client'

export default function SetAlertModal({ signal, onClose, onCreated }) {
  const [alertPrice, setAlertPrice] = useState('')
  const [validDays, setValidDays] = useState(30)
  const [notes, setNotes] = useState('')

  const mutation = useMutation({
    mutationFn: (data) => client.post('/alerts', data).then(r => r.data),
    onSuccess: onCreated,
  })

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-96 space-y-4">
        <h2 className="text-base font-semibold">Set Alert — {signal.symbol}</h2>
        <p className="text-sm text-gray-500">
          Signal date: {signal.scan_date || 'today'} · Close: ₹{signal.close_price.toLocaleString('en-IN', {minimumFractionDigits: 2})}
        </p>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Alert Price (₹) — trigger when LTP ≤ this price
          </label>
          <input
            type="number"
            step="0.05"
            value={alertPrice}
            onChange={e => setAlertPrice(e.target.value)}
            placeholder={`e.g. ${(signal.close_price * 0.95).toFixed(2)}`}
            className="w-full border rounded px-3 py-2 text-sm"
            autoFocus
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Valid for (days)</label>
          <input
            type="number"
            min="1"
            max="365"
            value={validDays}
            onChange={e => setValidDays(parseInt(e.target.value))}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>

        {mutation.isError && (
          <p className="text-sm text-red-600">{mutation.error.message}</p>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded">
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate({
              symbol: signal.symbol,
              security_id: signal.security_id,
              signal_date: signal.scan_date,
              alert_price: parseFloat(alertPrice),
              valid_days: validDays,
              notes: notes || null,
            })}
            disabled={!alertPrice || mutation.isPending}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Saving…' : 'Create Alert'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

## Done When
- `/signals` loads with the most recent scan date selected and signals listed
- Date dropdown shows all available scan dates
- Clicking "Set Alert" opens the modal; submitting creates the alert and shows "Alert set" badge
- "Run Scanner Now" button triggers scan and refreshes the date list
- Return % is shown in green with "+" prefix
- Prices formatted in Indian notation with ₹ symbol
