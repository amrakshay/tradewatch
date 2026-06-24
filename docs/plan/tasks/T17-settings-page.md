# T17 — Settings Page

| Field | Value |
|-------|-------|
| Phase | 2 |
| Depends on | T15, T16 |
| Unlocks | T22 |
| Estimate | 1 day |
| Status | ⬜ Not Started |

## Goal
Implement the Settings page with 4 sections: Scanner Settings, Dhan API, Telegram, and Stock Universe. All fields save to the backend config API. Sensitive token fields use masked display with a "change" flow.

## Files to Create / Modify

- `frontend/src/pages/Settings.jsx` (replace placeholder)
- `frontend/src/api/config.js`
- `frontend/src/api/stocks.js`

## Steps

### 1. `frontend/src/api/config.js`

```js
import client from './client'

export const getConfig = () => client.get('/config').then(r => r.data)
export const updateConfig = (data) => client.put('/config', data).then(r => r.data)
export const testDhanConnection = () => client.post('/config/test-dhan').then(r => r.data)
export const renewDhanToken = () => client.post('/config/renew-token').then(r => r.data)
export const testTelegram = () => client.post('/config/test-telegram').then(r => r.data)
```

### 2. `frontend/src/api/stocks.js`

```js
import client from './client'

export const getStocks = (activeOnly = true) =>
  client.get('/stocks', { params: { active: activeOnly } }).then(r => r.data)
export const addStock = (data) => client.post('/stocks', data).then(r => r.data)
export const toggleStock = (id, is_active) =>
  client.patch(`/stocks/${id}`, null, { params: { is_active } }).then(r => r.data)
export const deleteStock = (id) => client.delete(`/stocks/${id}`).then(r => r.data)
export const syncNifty500 = () => client.post('/stocks/sync-nifty500').then(r => r.data)
```

### 3. `frontend/src/pages/Settings.jsx`

Structure (React Query + shadcn/ui):

```
Settings
├── ScannerSettingsCard
│   ├── scan_time (time input)
│   ├── scan_percentage (number input)
│   └── scan_days (number input)
│
├── DhanApiCard
│   ├── dhan_client_id (text input)
│   ├── dhan_access_token (password + "Change Token" flow)
│   ├── token_status badge (valid / expiring / invalid)
│   ├── token_expires_at display
│   ├── "Test Connection" button
│   └── "Renew Token" button
│
├── TelegramCard
│   ├── telegram_bot_token (password + "Change Token" flow)
│   ├── telegram_chat_id (text input)
│   └── "Send Test Message" button
│
└── StockUniverseCard
    ├── "Sync Nifty 500" button (shows matched/unmatched counts)
    ├── "Add Custom Stock" button (modal)
    └── Stock table (symbol, name, universe_tag, toggle, delete)
```

#### Token "Change" UX pattern

Masked display value (e.g. `****abc1`) is shown in a disabled input. A "Change" button replaces it with a real password input (blank) where the user can type the new token. Submitting sends only the new value if non-empty; cancelling restores the masked display. This prevents accidental overwrites.

```jsx
function TokenField({ label, maskedValue, fieldName, onSave }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')

  if (!editing) {
    return (
      <div className="flex items-center gap-2">
        <input
          type="password"
          value={maskedValue || '(not set)'}
          disabled
          className="flex-1 border rounded px-3 py-2 text-sm bg-gray-50 text-gray-500"
        />
        <button
          onClick={() => setEditing(true)}
          className="text-sm text-blue-600 hover:underline"
        >
          Change
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="password"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder={`Enter new ${label}`}
        className="flex-1 border rounded px-3 py-2 text-sm"
        autoFocus
      />
      <button
        onClick={() => { if (value) onSave(fieldName, value); setEditing(false); setValue(''); }}
        className="text-sm text-green-700 font-medium hover:underline"
      >
        Save
      </button>
      <button
        onClick={() => { setEditing(false); setValue(''); }}
        className="text-sm text-gray-500 hover:underline"
      >
        Cancel
      </button>
    </div>
  )
}
```

#### Scanner Settings card (inline save on blur or explicit save button)

Each field saves individually via `PATCH /api/config`. Show a "Saved ✓" toast on success.

```jsx
function ScannerSettingsCard({ config, onUpdate }) {
  const [scanTime, setScanTime] = useState(config.scan_time)
  const [pct, setPct] = useState(config.scan_percentage)
  const [days, setDays] = useState(config.scan_days)

  const save = async () => {
    await updateConfig({ scan_time: scanTime, scan_percentage: pct, scan_days: days })
    toast.success('Scanner settings saved')
  }

  return (
    <Card>
      <CardHeader><CardTitle>Scanner Settings</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <Label>Scan Time (IST)</Label>
        <Input type="time" value={scanTime} onChange={e => setScanTime(e.target.value)} />
        <Label>Return Threshold (%)</Label>
        <Input type="number" step="0.5" min="1" value={pct}
               onChange={e => setPct(parseFloat(e.target.value))} />
        <Label>Trading Days</Label>
        <Input type="number" min="1" max="30" value={days}
               onChange={e => setDays(parseInt(e.target.value))} />
        <Button onClick={save}>Save</Button>
      </CardContent>
    </Card>
  )
}
```

### 4. `frontend/src/api/stocks.js` Stock Universe Card

```jsx
function StockUniverseCard() {
  const { data: stocks, refetch } = useQuery(['stocks'], () => getStocks(false))
  const [syncing, setSyncing] = useState(false)

  const handleSync = async () => {
    setSyncing(true)
    const result = await syncNifty500()
    toast.success(`Synced: ${result.matched} matched, ${result.unmatched} unmatched`)
    refetch()
    setSyncing(false)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle>Stock Universe</CardTitle>
          <Button variant="outline" onClick={handleSync} disabled={syncing}>
            {syncing ? 'Syncing…' : 'Sync Nifty 500'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2">Symbol</th>
              <th className="text-left">Name</th>
              <th className="text-left">Universe</th>
              <th className="text-center">Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {stocks?.map(s => (
              <tr key={s.id} className="border-b last:border-0">
                <td className="py-2 font-mono">{s.symbol}</td>
                <td className="text-gray-600 truncate max-w-xs">{s.name}</td>
                <td>{s.universe_tag}</td>
                <td className="text-center">
                  <input type="checkbox" checked={s.is_active}
                    onChange={e => toggleStock(s.id, e.target.checked).then(() => refetch())} />
                </td>
                <td>
                  <button onClick={() => deleteStock(s.id).then(() => refetch())}
                    className="text-red-500 hover:underline text-xs">
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
```

## Done When
- Navigating to `/settings` shows 4 cards with populated data from config API
- Changing scan_time and clicking Save updates the scheduler (verify via `GET /api/scheduler/status`)
- "Change Token" flow for Dhan token allows entering a new token; masked value shows after save
- "Test Connection" shows success/error inline
- "Send Test Message" delivers a Telegram message and shows success/failure
- Sync Nifty 500 shows a result toast with counts; stock table populates
- Stock active toggle immediately updates `is_active` in DB
