import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSignalDates, getSignals, runScanner, getScannerProgress } from '../api/signals'
import SignalTable from '../components/signals/SignalTable'
import SetAlertModal from '../components/signals/SetAlertModal'

export default function Signals() {
  const qc = useQueryClient()
  const [selectedDate, setSelectedDate] = useState(null)
  const [alertTarget, setAlertTarget] = useState(null)

  const { data: dates = [] } = useQuery({
    queryKey: ['signal-dates'],
    queryFn: getSignalDates,
  })

  useEffect(() => {
    if (!selectedDate && dates.length > 0) {
      setSelectedDate(dates[0])
    }
  }, [dates, selectedDate])

  const { data: signalsData, isLoading } = useQuery({
    queryKey: ['signals', selectedDate],
    queryFn: () => getSignals(selectedDate),
    enabled: !!selectedDate,
  })

  const scanMutation = useMutation({
    mutationFn: runScanner,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['signal-dates'] })
      qc.invalidateQueries({ queryKey: ['signals'] })
    },
  })

  const { data: progress } = useQuery({
    queryKey: ['scanner-progress'],
    queryFn: getScannerProgress,
    enabled: scanMutation.isPending,
    refetchInterval: scanMutation.isPending ? 1500 : false,
  })

  const pct = progress?.total > 0
    ? Math.round((progress.completed / progress.total) * 100)
    : 0

  return (
    <div className="space-y-4">
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

      {scanMutation.isPending && progress?.status === 'running' && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-blue-700 font-medium">
              Scanning Nifty 500 — {progress.completed} / {progress.total} stocks
            </span>
            <span className="text-blue-600 font-semibold">{pct}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-blue-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-blue-500">
            {progress.signals_found} signal{progress.signals_found !== 1 ? 's' : ''} found so far
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : (
        <SignalTable
          signals={signalsData?.signals || []}
          onSetAlert={setAlertTarget}
        />
      )}

      {alertTarget && (
        <SetAlertModal
          signal={alertTarget}
          scanDate={selectedDate}
          onClose={() => setAlertTarget(null)}
          onCreated={() => {
            setAlertTarget(null)
            qc.invalidateQueries({ queryKey: ['signals', selectedDate] })
          }}
        />
      )}
    </div>
  )
}
