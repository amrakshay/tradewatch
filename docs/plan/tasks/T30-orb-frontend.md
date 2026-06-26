# T30 — ORB Frontend Pages

**Phase:** ORB Phase 2
**Depends on:** T16 (React scaffold), T27 (ORB signal API), T28 (ORB backtest API)
**Blocks:** —

---

## Goal

Add three ORB-specific UI areas to the existing React frontend:
1. **ORB Signals page** — view today's (or any date's) signals
2. **ORB Backtest page** — run historical ORB analysis
3. **Settings — ORB section** — manage universe instruments and thresholds

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `frontend/src/api/orb.js` |
| Create | `frontend/src/pages/ORBSignals.jsx` |
| Create | `frontend/src/pages/ORBBacktest.jsx` |
| Create | `frontend/src/components/orb/SignalCard.jsx` |
| Create | `frontend/src/components/orb/BacktestResults.jsx` |
| Create | `frontend/src/components/orb/AddInstrumentModal.jsx` |
| Modify | `frontend/src/App.jsx` (add routes) |
| Modify | `frontend/src/components/layout/Sidebar.jsx` (add nav items) |
| Modify | `frontend/src/pages/Settings.jsx` (add ORB section) |

---

## 1. API Client (`frontend/src/api/orb.js`)

```js
import client from './client'

export const orbApi = {
  // Universe
  getUniverse:       ()     => client.get('/orb/universe'),
  addInstrument:     (data) => client.post('/orb/universe', data),
  toggleInstrument:  (id, is_active) => client.patch(`/orb/universe/${id}`, null, { params: { is_active } }),
  deleteInstrument:  (id)   => client.delete(`/orb/universe/${id}`),

  // Signals
  getSignalDates:    ()     => client.get('/orb/signals/dates'),
  getSignals:        (date) => client.get('/orb/signals', { params: { date } }),
  getLatestSignals:  ()     => client.get('/orb/signals/latest'),
  runScanNow:        ()     => client.post('/orb/scanner/run'),

  // Backtest
  runBacktest:       (req)  => client.post('/orb/backtest', req),
}
```

---

## 2. ORB Signals Page (`frontend/src/pages/ORBSignals.jsx`)

**Layout:**
```
[ Run ORB Check Now ]                    [ Date Picker ▼ ]

┌──────────── NIFTY 50 ────────────────────────────────────────┐
│  🟢 LONG   Signal Price: ₹22,150.75   Breakout: 10:05 IST   │
│                                                              │
│  Opening Range:  ₹21,980.00 – ₹22,130.00                    │
│  Breakout Volume: 1,25,000  (prev candle: 82,000)           │
│                                                              │
│  First Candle (Bullish)  ⚡ Strong Setup                     │
│  Body: 72%   Volume Ratio: 1.8×                              │
└──────────────────────────────────────────────────────────────┘

┌──────────── BANKNIFTY ───────────────────────────────────────┐
│  🔴 SHORT  Signal Price: ₹47,890.00   Breakout: 11:25 IST   │
│  …                                                           │
└──────────────────────────────────────────────────────────────┘

[ No more signals for this date ]
```

**Key behaviours:**
- Defaults to today (polls `GET /orb/signals/latest`)
- Date picker loads `GET /orb/signals/dates` to disable dates with no signals
- "Run ORB Check Now" button calls `POST /orb/scanner/run` and refreshes
- Each signal renders as a `<SignalCard>` component
- Empty state: "No ORB signals for [date]. Market may have been closed or no breakout occurred."

---

## 3. SignalCard Component (`frontend/src/components/orb/SignalCard.jsx`)

Props: `signal` (ORBSignalResponse object)

```jsx
<div className="border rounded-lg p-4 space-y-3">
  {/* Header row */}
  <div className="flex justify-between items-center">
    <span className="font-semibold text-lg">{signal.symbol}</span>
    <div className="flex gap-2">
      <Badge color={signal.signal_direction === 'LONG' ? 'green' : 'red'}>
        {signal.signal_direction === 'LONG' ? '🟢 LONG' : '🔴 SHORT'}
      </Badge>
      {signal.first_candle_strong && <Badge color="yellow">⚡ Strong Setup</Badge>}
    </div>
  </div>

  {/* Signal price + time */}
  <div className="grid grid-cols-2 gap-4 text-sm">
    <div><span className="text-gray-500">Signal Price</span>
         <p className="font-mono font-semibold">₹{signal.signal_price.toLocaleString('en-IN', {minimumFractionDigits: 2})}</p></div>
    <div><span className="text-gray-500">Breakout Time</span>
         <p>{signal.breakout_time} IST</p></div>
  </div>

  {/* Opening range */}
  <div className="text-sm">
    <span className="text-gray-500">Opening Range (15-min)</span>
    <p>₹{signal.orb_low.toLocaleString('en-IN')} – ₹{signal.orb_high.toLocaleString('en-IN')}</p>
  </div>

  {/* Volume */}
  <div className="text-sm">
    <span className="text-gray-500">Breakout Volume</span>
    <p>{signal.breakout_candle_volume.toLocaleString('en-IN')}
       <span className="text-gray-400"> (prev: {signal.prev_candle_volume.toLocaleString('en-IN')})</span></p>
  </div>

  {/* First candle */}
  <div className="text-sm bg-gray-50 rounded p-2">
    <span className="text-gray-500">First Candle</span>
    <span className="ml-2 capitalize">{signal.first_candle_direction}</span>
    <span className="ml-3">Body: {(signal.first_candle_body_pct * 100).toFixed(0)}%</span>
    <span className="ml-3">Vol Ratio: {signal.first_candle_volume_ratio.toFixed(1)}×</span>
  </div>
</div>
```

---

## 4. ORB Backtest Page (`frontend/src/pages/ORBBacktest.jsx`)

**Form:**
- Instrument dropdown (from `GET /orb/universe`)
- Date range: presets (1 month, 3 months, 6 months) + custom from/to
- Body % threshold (number input, 0–100%, default from config)
- Volume ratio threshold (number input, default from config)
- Submit button + loading state

**Results:**
```
Summary
  Total Trading Days: 123
  Long Signals: 34 (27.6%)     Short Signals: 28 (22.8%)
  Strong Setup Days: 19 (15.4%)

[ Filter: Show all ▼ ]   [ Strong setups only ]

Date        ORB Range              First Candle     Long Signal    Short Signal
2024-01-15  21,980 – 22,130  Bullish ⚡  10:05  ₹22,150   —
2024-01-14  47,200 – 47,650  Bearish         —              11:30 ₹47,100
...
```

- "Strong setups only" toggle filters to `first_candle_strong === true`
- Long/Short columns show time + price or "—" if not triggered

---

## 5. Settings — ORB Section (extends `frontend/src/pages/Settings.jsx`)

New card at the bottom of the Settings page:

```
┌─── ORB Strategy ──────────────────────────────────────┐
│                                                        │
│  Body % Threshold:    [ 0.60 ]   (0.0 – 1.0)         │
│  Volume Ratio:        [ 1.50 ]   (e.g. 1.5 = 150%)   │
│  [ Save ]                                              │
│                                                        │
│  Universe                            [ + Add ]         │
│  ┌────────────┬────────────┬─────────┬───────────────┐ │
│  │ Symbol     │ Seg / Type │ Active  │ Actions       │ │
│  ├────────────┼────────────┼─────────┼───────────────┤ │
│  │ NIFTY 50   │ IDX_I/INDEX│  ✓      │ [Disable][✕]  │ │
│  │ BANKNIFTY  │ IDX_I/INDEX│  ✓      │ [Disable][✕]  │ │
│  └────────────┴────────────┴─────────┴───────────────┘ │
└────────────────────────────────────────────────────────┘
```

**Add Instrument Modal fields:**
- Symbol (text, e.g. "MIDCAPNIFTY")
- Security ID (text, e.g. "11536")
- Exchange Segment (dropdown: IDX_I, NSE_EQ, BSE_EQ)
- Instrument Type (dropdown: INDEX, EQUITY)

---

## Routing (add to `App.jsx`)

```jsx
import ORBSignals  from './pages/ORBSignals'
import ORBBacktest from './pages/ORBBacktest'

<Route path="/orb/signals"  element={<ORBSignals />} />
<Route path="/orb/backtest" element={<ORBBacktest />} />
```

## Sidebar (add to `Sidebar.jsx`)

```jsx
{ label: 'ORB Signals',  href: '/orb/signals',  icon: TrendingUp }
{ label: 'ORB Backtest', href: '/orb/backtest',  icon: BarChart2  }
```

---

## Done When

- [ ] ORB Signals page loads and shows today's signals (or "no signals" message)
- [ ] Date picker shows only dates with signals; switching date loads correct data
- [ ] "Run ORB Check Now" button triggers scan and refreshes
- [ ] Signal cards display all fields correctly (price, time, range, volume, first candle)
- [ ] Long signals have green badge; Short have red badge
- [ ] Strong setup badge shows only when `first_candle_strong === true`
- [ ] ORB Backtest page form submits and shows results table
- [ ] "Strong setups only" filter works client-side
- [ ] Settings ORB section saves thresholds and manages universe
- [ ] Add/disable/delete instrument works without page reload
- [ ] ORB nav items appear in sidebar
