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

  const oneWeekAgo = new Date()
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
  const triggeredThisWeek = triggeredAlerts.filter(a =>
    a.triggered_at && new Date(a.triggered_at) >= oneWeekAgo
  )

  const dailyScanJob = schedulerStatus?.jobs?.find(j => j.id === 'daily_scan')

  const recentSignals = (latestSignals?.signals || []).slice(0, 5)

  const recentTriggered = triggeredAlerts
    .filter(a => a.triggered_at)
    .sort((a, b) => new Date(b.triggered_at) - new Date(a.triggered_at))
    .slice(0, 5)

  return (
    <div className="space-y-6">
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

      <div className="grid grid-cols-2 gap-6">
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
