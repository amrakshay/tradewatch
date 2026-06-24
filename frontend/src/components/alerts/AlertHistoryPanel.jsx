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
              <div className="text-gray-500">{e.timestamp.slice(0, 16).replace('T', ' ')}</div>
              {e.price && <div className="text-gray-600">₹{e.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>}
              {e.note && <div className="text-gray-500 italic">{e.note}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
