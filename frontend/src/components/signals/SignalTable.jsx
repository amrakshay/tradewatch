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
              <td className="px-4 py-3 text-right">₹{s.close_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
              <td className="px-4 py-3 text-right text-gray-500">₹{s.start_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
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
