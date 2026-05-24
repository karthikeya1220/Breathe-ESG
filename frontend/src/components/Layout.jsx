import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Leaf, LayoutDashboard, Upload, Briefcase,
  LogOut, ChevronRight, User
} from 'lucide-react'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Review Queue' },
  { to: '/upload',    icon: Upload,          label: 'Upload Data' },
  { to: '/jobs',      icon: Briefcase,       label: 'Ingestion Jobs' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-surface-950 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 flex flex-col bg-surface-900 border-r border-surface-700 flex-shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-surface-700">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-white leading-none">Breathe ESG</div>
            <div className="text-xs text-gray-500 mt-0.5">Emissions Platform</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group
                 ${isActive
                   ? 'bg-brand-900/40 text-brand-400 border border-brand-800/50'
                   : 'text-gray-400 hover:text-white hover:bg-surface-700'}`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-surface-700">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface-800">
            <div className="w-7 h-7 rounded-full bg-brand-800 flex items-center justify-center flex-shrink-0">
              <User className="w-3.5 h-3.5 text-brand-300" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-white truncate">{user?.username}</div>
              <div className="text-xs text-gray-500 truncate">{user?.role}</div>
            </div>
          </div>
          <button
            id="logout-btn"
            onClick={handleLogout}
            className="mt-2 w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-950/30 transition-all"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>

        {/* Org pill */}
        {user?.org && (
          <div className="px-4 pb-4">
            <div className="text-xs text-gray-500 px-1 mb-1">Organization</div>
            <div className="bg-surface-700 rounded-lg px-3 py-2">
              <div className="text-xs font-medium text-gray-300 truncate">{user.org.name}</div>
            </div>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
