# T19 — Alerts Page

| Field | Value |
|-------|-------|
| Phase | 3 |
| Depends on | T12, T16 |
| Unlocks | T21, T22 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the Alerts page with a tab bar (Active / Triggered / Expired / All), alert management actions (edit price/days, delete), and a slide-out history panel showing the event log for each alert.

## Files to Create / Modify

- `frontend/src/pages/Alerts.jsx` (replace placeholder)
- `frontend/src/api/alerts.js`
- `frontend/src/components/alerts/AlertTable.jsx`
- `frontend/src/components/alerts/AlertHistoryPanel.jsx`
- `frontend/src/components/alerts/EditAlertModal.jsx`

## Steps

### 1. `frontend/src/api/alerts.js`

```js
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
```

### 2. `frontend/src/pages/Alerts.jsx`

```jsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAlerts, deleteAlert } from '../api/alerts'
import AlertTable from '../components/alerts/AlertTable'
import AlertHistoryPanel from '../components/alerts/AlertHistoryPanel'
import EditAlertModal from '../components/alerts/EditAlertModal'

const TABS = [
  { label: 'Active',    value: 'active'    },
  { label: 'Triggered', value: 'triggered' },
  { label: 'Expired',   value: 'expired'   },
  { label: 'All',       value: null        },
]

export default function Alerts() {
  const qc = useQueryClient()
  const [tab, setTab] = useState('active')
  const [historyAlert, setHistoryAlert] = useState(null)
  const [editAlert, setEditAlert] = useState(null)

  const activeTab = TABS.find(t => t.label.toLowerCase() === tab)
  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts', activeTab?.value],
    queryFn: () => getAlerts(activeTab?.value),
    refetchInterval: 60_000,  // refresh every minute
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAlert,
    onSuccess: () => qc.invalidateQueries(['alerts']),
  })

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map(t => (
          <button
            key={t.label}
            onClick={() => setTab(t.label.toLowerCase())}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.label.toLowerCase()
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Alert table */}
      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : (
        <AlertTable
          alerts={alerts}
          onViewHistory={setHistoryAlert}
          onEdit={setEditAlert}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      )}

      {/* History slide-out */}
      {historyAlert && (
        <AlertHistoryPanel
          alert={historyAlert}
          onClose={() => setHistoryAlert(null)}
        />
      )}

      {/* Edit modal */}
      {editAlert && (
        <EditAlertModal
          alert={editAlert}
          onClose={() => setEditAlert(null)}
          onUpdated={() => {
            setEditAlert(null)
            qc.invalidateQueries(['alerts'])
          }}
        />
      )}
    </div>
  )
}
```

### 3. `frontend/src/components/alerts/AlertTable.jsx`

Columns: Symbol · Signal Date · Alert Price · Created · Expires · Status · Triggered Price · Actions

```jsx
export default function AlertTable({ alerts, onViewHistory, onEdit, onDelete }) {
  if (!alerts.length) {
    return <p className="text-gray-400 text-sm">No alerts.</p>
  }

  const statusColor = {
    active: 'bg-green-100 text-green-700',
    triggered: 'bg-blue-100 text-blue-700',
    expired: 'bg-gray-100 text-gray-500',
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            {['Symbol','Signal Date','Alert Price','Created','Expires','Status','Triggered','Actions']
              .map(h => (
              <th key={h} className="text-left px-4 py-3 font-medium text-gray-600 whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {alerts.map(a => (
            <tr key={a.id} className="border-b last:border-0 hover:bg-gray-50">
              <td className="px-4 py-3 font-mono font-medium">{a.symbol}</td>
              <td className="px-4 py-3 text-gray-600">{a.signal_date}</td>
              <td className="px-4 py-3">₹{a.alert_price.toLocaleString('en-IN',{minimumFractionDigits:2})}</td>
              <td className="px-4 py-3 text-gray-500">{a.created_at.slice(0,10)}</td>
              <td className="px-4 py-3 text-gray-500">{a.expires_at.slice(0,10)}</td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[a.status] || 'bg-gray-100 text-gray-500'}`}>
                  {a.status}
                </span>
              </td>
              <td className="px-4 py-3">
                {a.triggered_price
                  ? `₹${a.triggered_price.toLocaleString('en-IN',{minimumFractionDigits:2})}`
                  : '—'}
              </td>
              <td className="px-4 py-3">
                <div className="flex gap-2">
                  <button onClick={() => onViewHistory(a)}
                    className="text-xs text-blue-600 hover:underline">History</button>
                  {a.status === 'active' && (
                    <button onClick={() => onEdit(a)}
                      className="text-xs text-gray-600 hover:underline">Edit</button>
                  )}
                  <button onClick={() => onDelete(a.id)}
                    className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

### 4. `frontend/src/components/alerts/AlertHistoryPanel.jsx`

```jsx
import { useQuery } from '@tanstack/react-query'
import { getAlertHistory } from '../../api/alerts'

export default function AlertHistoryPanel({ alert, onClose }) {
  const { data: history = [] } = useQuery({
    queryKey: ['alert-history', alert.id],
    queryFn: () => getAlertHistory(alert.id),
  })

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-xl border-l border-gray-200 flex flex-col z-40">
      <div className="flex items-center justify-between px-6 py-4 border-b">
        <h2 className="font-semibold">History — {alert.symbol}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {history.length === 0 && (
          <p className="text-gray-400 text-sm">No events yet.</p>
        )}
        {history.map(e => (
          <div key={e.id} className="flex gap-3 text-sm">
            <div className="w-1 bg-gray-200 rounded" />
            <div>
              <div className="font-medium capitalize">{e.event_type}</div>
              <div className="text-gray-500">{e.timestamp.slice(0,16).replace('T',' ')}</div>
              {e.price && <div className="text-gray-600">₹{e.price.toLocaleString('en-IN',{minimumFractionDigits:2})}</div>}
              {e.note && <div className="text-gray-500 italic">{e.note}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

### 5. `frontend/src/components/alerts/EditAlertModal.jsx`

```jsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { updateAlert } from '../../api/alerts'

export default function EditAlertModal({ alert, onClose, onUpdated }) {
  const [price, setPrice] = useState(alert.alert_price)
  const [days, setDays] = useState(alert.valid_days)
  const [notes, setNotes] = useState(alert.notes || '')

  const mutation = useMutation({
    mutationFn: (data) => updateAlert(alert.id, data),
    onSuccess: onUpdated,
  })

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-80 space-y-4">
        <h2 className="text-base font-semibold">Edit Alert — {alert.symbol}</h2>

        <div>
          <label className="block text-sm font-medium mb-1">Alert Price (₹)</label>
          <input type="number" step="0.05" value={price}
            onChange={e => setPrice(parseFloat(e.target.value))}
            className="w-full border rounded px-3 py-2 text-sm" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Valid for (days)</label>
          <input type="number" min="1" value={days}
            onChange={e => setDays(parseInt(e.target.value))}
            className="w-full border rounded px-3 py-2 text-sm" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Notes</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)}
            rows={2} className="w-full border rounded px-3 py-2 text-sm" />
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded">Cancel</button>
          <button
            onClick={() => mutation.mutate({ alert_price: price, valid_days: days, notes: notes || null })}
            disabled={mutation.isPending}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

## Done When
- `/alerts` loads with Active tab showing active alerts
- Tab switching filters by status
- "History" opens the slide-out panel with event log
- "Edit" opens modal; price/days update and history event logged
- "Delete" removes alert immediately from list
- Status badge uses correct color coding (green=active, blue=triggered, gray=expired)
- Table auto-refreshes every 60 seconds
