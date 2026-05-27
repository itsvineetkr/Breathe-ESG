import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Upload, Database, ClipboardList, CheckCircle, XCircle,
  BarChart2, ScrollText, Users, Settings, LogOut, Leaf
} from 'lucide-react'

const navItem = (to, icon, label) => ({ to, icon, label })

function NavItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? 'bg-brand-600 text-white'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`
      }
    >
      <Icon size={17} />
      {label}
    </NavLink>
  )
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside className="w-60 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <Leaf className="text-brand-600" size={22} />
          <span className="font-bold text-gray-900 text-lg">Breathe ESG</span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5 pl-7">{user?.organization?.name}</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {isAdmin && (
          <NavItem to="/upload" icon={Upload} label="Upload Data" />
        )}

        <div className="pt-2">
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Uploads</p>
          <NavItem to="/uploads/sap" icon={Database} label="SAP" />
          <NavItem to="/uploads/utility" icon={Database} label="Utility" />
          <NavItem to="/uploads/travel" icon={Database} label="Travel" />
        </div>

        <div className="pt-2">
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Review</p>
          <NavItem to="/review" icon={ClipboardList} label="Review Queue" />
          <NavItem to="/approved" icon={CheckCircle} label="Approved" />
          <NavItem to="/rejected" icon={XCircle} label="Rejected" />
        </div>

        <div className="pt-2">
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Analysis</p>
          <NavItem to="/reports" icon={BarChart2} label="Reports" />
          {isAdmin && <NavItem to="/audit" icon={ScrollText} label="Audit Logs" />}
        </div>

        {isAdmin && (
          <div className="pt-2">
            <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Admin</p>
            <NavItem to="/team" icon={Users} label="Team" />
            <NavItem to="/settings" icon={Settings} label="Settings" />
          </div>
        )}
      </nav>

      {/* User profile */}
      <div className="px-3 py-4 border-t border-gray-100">
        <div className="flex items-center gap-2 px-2 mb-2">
          <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-semibold text-sm">
            {user?.first_name?.[0] || user?.email?.[0] || '?'}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
