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
            {['Symbol', 'Signal Date', 'Alert Price', 'Created', 'Expires', 'Status', 'Triggered', 'Actions']
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
              <td className="px-4 py-3">₹{a.alert_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
              <td className="px-4 py-3 text-gray-500">{a.created_at.slice(0, 10)}</td>
              <td className="px-4 py-3 text-gray-500">{a.expires_at.slice(0, 10)}</td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[a.status] || 'bg-gray-100 text-gray-500'}`}>
                  {a.status}
                </span>
              </td>
              <td className="px-4 py-3">
                {a.triggered_price
                  ? `₹${a.triggered_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
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
