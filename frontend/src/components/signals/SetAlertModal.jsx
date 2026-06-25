import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import client from '../../api/client'

export default function SetAlertModal({ signal, scanDate, onClose, onCreated }) {
  const [alertPrice, setAlertPrice] = useState('')
  const [validDays, setValidDays] = useState(30)
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState({})

  const mutation = useMutation({
    mutationFn: (data) => client.post('/alerts', data).then(r => r.data),
    onSuccess: onCreated,
  })

  function validate() {
    const errs = {}
    if (!alertPrice || isNaN(parseFloat(alertPrice))) {
      errs.alertPrice = 'Alert price is required'
    } else if (parseFloat(alertPrice) <= 0) {
      errs.alertPrice = 'Alert price must be greater than 0'
    }
    if (!validDays || isNaN(parseInt(validDays)) || parseInt(validDays) < 1) {
      errs.validDays = 'Must be at least 1 day'
    }
    return errs
  }

  function handleSubmit() {
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }
    setErrors({})
    mutation.mutate({
      symbol: signal.symbol,
      security_id: signal.security_id,
      signal_date: signal.scan_date || scanDate,
      alert_price: parseFloat(alertPrice),
      valid_days: parseInt(validDays),
      notes: notes || null,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-96 space-y-4">
        <h2 className="text-base font-semibold">Set Alert — {signal.symbol}</h2>
        <p className="text-sm text-gray-500">
          Signal date: {signal.scan_date || scanDate || 'today'} · Close: ₹{signal.close_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
        </p>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Alert Price (₹) — trigger when LTP ≤ this price
          </label>
          <input
            type="number"
            step="0.05"
            value={alertPrice}
            onChange={e => { setAlertPrice(e.target.value); setErrors(prev => ({ ...prev, alertPrice: null })) }}
            placeholder={`e.g. ${(signal.close_price * 0.95).toFixed(2)}`}
            className={`w-full border rounded px-3 py-2 text-sm ${errors.alertPrice ? 'border-red-400 focus:ring-red-300' : ''}`}
            autoFocus
          />
          {errors.alertPrice && (
            <p className="text-xs text-red-600 mt-1">{errors.alertPrice}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Valid for (days)</label>
          <input
            type="number"
            min="1"
            max="365"
            value={validDays}
            onChange={e => { setValidDays(e.target.value); setErrors(prev => ({ ...prev, validDays: null })) }}
            className={`w-full border rounded px-3 py-2 text-sm ${errors.validDays ? 'border-red-400' : ''}`}
          />
          {errors.validDays && (
            <p className="text-xs text-red-600 mt-1">{errors.validDays}</p>
          )}
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
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {mutation.error.message}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={mutation.isPending}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Saving…' : 'Create Alert'}
          </button>
        </div>
      </div>
    </div>
  )
}
