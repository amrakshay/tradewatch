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
