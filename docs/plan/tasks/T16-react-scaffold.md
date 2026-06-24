# T16 — React App Scaffold (Layout + Routing)

| Field | Value |
|-------|-------|
| Phase | 1 |
| Depends on | T01 |
| Unlocks | T17, T18, T19, T20, T21 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Set up the React app shell: routing, side navigation, top bar, Axios client, React Query provider, and placeholder page components. All 5 pages routed but empty at this stage.

## Files to Create

- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/api/client.js`
- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/components/layout/TopBar.jsx`
- `frontend/src/pages/Dashboard.jsx` (placeholder)
- `frontend/src/pages/Signals.jsx` (placeholder)
- `frontend/src/pages/Alerts.jsx` (placeholder)
- `frontend/src/pages/Backtest.jsx` (placeholder)
- `frontend/src/pages/Settings.jsx` (placeholder)
- `frontend/src/index.css`

## Steps

### 1. `frontend/src/main.jsx`

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
)
```

### 2. `frontend/src/App.jsx`

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import TopBar from './components/layout/TopBar'
import Dashboard from './pages/Dashboard'
import Signals from './pages/Signals'
import Alerts from './pages/Alerts'
import Backtest from './pages/Backtest'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/signals" element={<Signals />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
```

### 3. `frontend/src/api/client.js`

```js
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    console.error('API error:', msg)
    return Promise.reject(new Error(msg))
  }
)

export default client
```

### 4. `frontend/src/components/layout/Sidebar.jsx`

```jsx
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Bell, BarChart2, Settings
} from 'lucide-react'

const nav = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/signals',   icon: TrendingUp,      label: 'Signals'   },
  { to: '/alerts',    icon: Bell,            label: 'Alerts'    },
  { to: '/backtest',  icon: BarChart2,       label: 'Backtest'  },
  { to: '/settings',  icon: Settings,        label: 'Settings'  },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
      <div className="px-6 py-5 font-bold text-lg text-gray-900 border-b border-gray-200">
        TradeWatch
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
```

### 5. `frontend/src/components/layout/TopBar.jsx`

```jsx
import { useLocation } from 'react-router-dom'

const titles = {
  '/':          'Dashboard',
  '/signals':   'Signals',
  '/alerts':    'Alerts',
  '/backtest':  'Backtest',
  '/settings':  'Settings',
}

export default function TopBar() {
  const { pathname } = useLocation()
  const title = titles[pathname] ?? 'TradeWatch'

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center px-6">
      <h1 className="text-base font-semibold text-gray-900">{title}</h1>
    </header>
  )
}
```

### 6. Placeholder pages

Each page file is a minimal stub — content added in T17–T21:

```jsx
// Example: frontend/src/pages/Dashboard.jsx
export default function Dashboard() {
  return <div className="text-gray-500">Dashboard — coming soon</div>
}
```

Repeat for `Signals.jsx`, `Alerts.jsx`, `Backtest.jsx`, `Settings.jsx`.

### 7. `frontend/src/index.css`

```css
@import "tailwindcss";
```

(Tailwind v4 single-import syntax with `@tailwindcss/vite` plugin)

## Done When
- `npm run dev` starts with no errors
- Navigating to `/`, `/signals`, `/alerts`, `/backtest`, `/settings` each renders the correct page title in TopBar
- Sidebar highlights the active route
- No console errors on load
