import { useLocation } from 'react-router-dom'

const titles = {
  '/':         'Dashboard',
  '/signals':  'Signals',
  '/alerts':   'Alerts',
  '/backtest': 'Backtest',
  '/settings': 'Settings',
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
