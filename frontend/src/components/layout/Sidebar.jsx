import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Bell, BarChart2, Settings
} from 'lucide-react'

const nav = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/signals',  icon: TrendingUp,      label: 'Signals'   },
  { to: '/alerts',   icon: Bell,            label: 'Alerts'    },
  { to: '/backtest', icon: BarChart2,       label: 'Backtest'  },
  { to: '/settings', icon: Settings,        label: 'Settings'  },
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
