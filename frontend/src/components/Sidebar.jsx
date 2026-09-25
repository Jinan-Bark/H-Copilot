import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Bed,
  ClipboardList,
  UserCog,
  Activity,
  TrendingUp
} from 'lucide-react'
import './Sidebar.css'

const navItems = [
  { path: '/',            icon: <LayoutDashboard size={20} />, label: 'Dashboard'   },
  { path: '/patients',   icon: <Users size={20} />,           label: 'Patients'    },
  { path: '/beds',       icon: <Bed size={20} />,             label: 'Beds'        },
  { path: '/assignments',icon: <ClipboardList size={20} />,   label: 'Assignments' },
  { path: '/staff',      icon: <UserCog size={20} />,         label: 'Staff'       },
  { path: '/forecast',   icon: <TrendingUp size={20} />,      label: 'Forecast'    },
]

function Sidebar() {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <Activity size={24} className="logo-icon" />
        <span className="logo-text">H-Copilot</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              isActive ? 'nav-item nav-item-active' : 'nav-item'
            }
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <p className="footer-text">Lebanese University</p>
        <p className="footer-sub">ED Platform v1.0</p>
      </div>
    </aside>
  )
}

export default Sidebar