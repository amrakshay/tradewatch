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
    refetchInterval: 60_000,
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
