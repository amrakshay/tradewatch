# T21 — Dashboard Page

| Field | Value |
|-------|-------|
| Phase | 4 |
| Depends on | T10, T12, T16 |
| Unlocks | T22 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Implement the Dashboard home page: stat cards (today's signals, active alerts, triggered this week), last scan status, recent signals list, and recent alert triggers list.

## Files to Create / Modify

- `frontend/src/pages/Dashboard.jsx` (replace placeholder)
- `frontend/src/api/dashboard.js`

## Steps

### 1. `frontend/src/api/dashboard.js`

```js
import client from './client'

// Returns latest signals (most recent scan date)
export const getLatestSignals = () =>
  client.get('/signals/latest').then(r => r.data)

// Returns alerts (for stats and recent triggers)
export const getAlerts = (status) =>
  client.get('/alerts', { params: status ? { status } : {} }).then(r => r.data)

// Returns scheduler status (last scan time)
export const getSchedulerStatus = () =>
  client.get('/scheduler/status').then(r => r.data)
```

### 2. `frontend/src/pages/Dashboard.jsx`

```jsx
import { useQuery } from '@tanstack/react-query'
import { getLatestSignals, getAlerts, getSchedulerStatus } from '../api/dashboard'
import { Link } from 'react-router-dom'

function StatCard({ label, value, sub, color = 'blue' }) {
  const colors = {
    blue:   'bg-blue-50 text-blue-700',
    green:  'bg-green-50 text-green-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    gray:   'bg-gray-50 text-gray-700',
  }
  return (
    <div className={`rounded-lg p-5 ${colors[color]}`}>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm font-medium mt-1">{label}</div>
      {sub && <div className="text-xs opacity-70 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const { data: latestSignals } = useQuery({
    queryKey: ['signals-latest'],
    queryFn: getLatestSignals,
    refetchInterval: 5 * 60_000,
  })

  const { data: activeAlerts = [] } = useQuery({
    queryKey: ['alerts', 'active'],
    queryFn: () => getAlerts('active'),
    refetchInterval: 60_000,
  })

  const { data: triggeredAlerts = [] } = useQuery({
    queryKey: ['alerts', 'triggered'],
    queryFn: () => getAlerts('triggered'),
    refetchInterval: 60_000,
  })

  const { data: schedulerStatus } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
    refetchInterval: 2 * 60_000,
  })

  // Triggered this week
  const oneWeekAgo = new Date()
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
  const triggeredThisWeek = triggeredAlerts.filter(a =>
    a.triggered_at && new Date(a.triggered_at) >= oneWeekAgo
  )

  // Last scan info
  const dailyScanJob = schedulerStatus?.jobs?.find(j => j.id === 'daily_scan')

  // Recent 5 signals
  const recentSignals = (latestSignals?.signals || []).slice(0, 5)

  // Recent 5 triggered alerts
  const recentTriggered = triggeredAlerts
    .filter(a => a.triggered_at)
    .sort((a, b) => new Date(b.triggered_at) - new Date(a.triggered_at))
    .slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Today's Signals"
          value={latestSignals?.count ?? '—'}
          sub={latestSignals?.date ? `on ${latestSignals.date}` : 'No scan yet'}
          color="blue"
        />
        <StatCard
          label="Active Alerts"
          value={activeAlerts.length}
          color="green"
        />
        <StatCard
          label="Triggered This Week"
          value={triggeredThisWeek.length}
          color="yellow"
        />
        <StatCard
          label="Next Scan"
          value={dailyScanJob?.next_run
            ? new Date(dailyScanJob.next_run).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
            : '—'}
          sub="IST (Mon–Fri)"
          color="gray"
        />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-2 gap-6">
        {/* Recent signals */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-gray-800">Recent Signals</h2>
            <Link to="/signals" className="text-xs text-blue-600 hover:underline">View all →</Link>
          </div>
          {recentSignals.length === 0 ? (
            <p className="text-gray-400 text-sm">No signals yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left pb-2 font-medium text-gray-600">Symbol</th>
                  <th className="text-right pb-2 font-medium text-gray-600">Return %</th>
                  <th className="text-right pb-2 font-medium text-gray-600">Close</th>
                </tr>
              </thead>
              <tbody>
                {recentSignals.map(s => (
                  <tr key={s.id} className="border-b last:border-0">
                    <td className="py-2 font-mono">{s.symbol}</td>
                    <td className="py-2 text-right text-green-600">+{s.return_pct.toFixed(2)}%</td>
                    <td className="py-2 text-right text-gray-600">
                      ₹{s.close_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Recent alert triggers */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-gray-800">Recent Triggers</h2>
            <Link to="/alerts" className="text-xs text-blue-600 hover:underline">View all →</Link>
          </div>
          {recentTriggered.length === 0 ? (
            <p className="text-gray-400 text-sm">No alerts triggered yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left pb-2 font-medium text-gray-600">Symbol</th>
                  <th className="text-right pb-2 font-medium text-gray-600">Alert ₹</th>
                  <th className="text-right pb-2 font-medium text-gray-600">Triggered ₹</th>
                </tr>
              </thead>
              <tbody>
                {recentTriggered.map(a => (
                  <tr key={a.id} className="border-b last:border-0">
                    <td className="py-2 font-mono">{a.symbol}</td>
                    <td className="py-2 text-right">
                      ₹{a.alert_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-2 text-right text-blue-600">
                      ₹{a.triggered_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
```

## Done When
- `/` loads with 4 stat cards: today's signal count, active alert count, triggered this week, next scan time
- Recent signals table shows top 5 from the latest scan
- Recent triggers table shows last 5 triggered alerts sorted by trigger time
- Both tables have "View all →" links to their respective pages
- Data auto-refreshes (signals every 5m, alerts every 1m, scheduler every 2m)
- When no scan has been run yet, "Today's Signals" shows `0` or `—` gracefully
