import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function BacktestResults({ result }) {
  const { symbol, total_trading_days, qualifying_days,
          pct_threshold, num_days, results } = result

  return (
    <div className="space-y-5">
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

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              {['Date', 'Close Price', 'Start Price', 'Return %'].map(h => (
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
                <td className="px-4 py-3">₹{r.close_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                <td className="px-4 py-3 text-gray-500">₹{r.start_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                <td className="px-4 py-3 text-green-600 font-medium">+{r.return_pct.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
