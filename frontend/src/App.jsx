import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Patients from './pages/Patients'
import Beds from './pages/Beds'
import Assignments from './pages/Assignments'
import Staff from './pages/Staff'
import './App.css'
import Forecast from './pages/Forecast'

function App() {
  return (
    <div className="app-container">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/beds" element={<Beds />} />
          <Route path="/assignments" element={<Assignments />} />
          <Route path="/staff" element={<Staff />} />
          <Route path="/forecast" element={<Forecast />} />
        </Routes>
      </main>
    </div>
  )
}

export default App