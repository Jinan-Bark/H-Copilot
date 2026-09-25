import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Activity, Bed, Users, UserCog,
  AlertTriangle, CheckCircle, Clock
} from 'lucide-react'
import './Dashboard.css'

const API = 'http://127.0.0.1:8000'

function StatCard({ icon, label, value, color }) {
  return (
    <div className="stat-card" style={{ borderTopColor: color }}>
      <div className="stat-icon" style={{ color }}>{icon}</div>
      <div className="stat-info">
        <p className="stat-label">{label}</p>
        <p className="stat-value">{value}</p>
      </div>
    </div>
  )
}

function Dashboard() {
  const [patients, setPatients]   = useState([])
  const [beds, setBeds]           = useState([])
  const [nurses, setNurses]       = useState([])
  const [doctors, setDoctors]     = useState([])
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [p, b, n, d] = await Promise.all([
          axios.get(`${API}/patients`),
          axios.get(`${API}/beds`),
          axios.get(`${API}/nurses`),
          axios.get(`${API}/doctors`),
        ])
        setPatients(p.data)
        setBeds(b.data)
        setNurses(n.data)
        setDoctors(d.data)
      } catch (err) {
        console.error('Error fetching data:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const totalBeds      = beds.length
  const availableBeds  = beds.filter(b => b.bed_status === 'Available').length
  const occupiedBeds   = beds.filter(b => b.bed_status === 'Occupied').length
  const waitingPatients= patients.filter(p => p.status === 'waiting').length
  const admittedPatients = patients.filter(p => p.status === 'admitted').length
  const criticalWaiting= patients.filter(p => p.status === 'waiting' && p.acuity <= 2).length
  const occupancyRate  = totalBeds > 0 ? Math.round((occupiedBeds / totalBeds) * 100) : 0

  if (loading) return <div className="loading">Loading...</div>

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Emergency Department — Live Overview</p>
      </div>

      {/* Critical Alert */}
      {criticalWaiting > 0 && (
        <div className="alert-banner">
          <AlertTriangle size={18} />
          <span>{criticalWaiting} critical patient{criticalWaiting > 1 ? 's' : ''} (ESI 1-2) waiting for a bed — immediate action required</span>
        </div>
      )}

      {/* Stat Cards */}
      <div className="stats-grid">
        <StatCard
          icon={<Bed size={24} />}
          label="Available Beds"
          value={`${availableBeds} / ${totalBeds}`}
          color="#00c896"
        />
        <StatCard
          icon={<Activity size={24} />}
          label="Occupancy Rate"
          value={`${occupancyRate}%`}
          color="#0096ff"
        />
        <StatCard
          icon={<Clock size={24} />}
          label="Waiting Patients"
          value={waitingPatients}
          color="#f59e0b"
        />
        <StatCard
          icon={<CheckCircle size={24} />}
          label="Admitted Patients"
          value={admittedPatients}
          color="#10b981"
        />
        <StatCard
          icon={<Users size={24} />}
          label="Total Nurses"
          value={nurses.length}
          color="#a855f7"
        />
        <StatCard
          icon={<UserCog size={24} />}
          label="Total Doctors"
          value={doctors.length}
          color="#ec4899"
        />
      </div>

      {/* Bed Status per Ward */}
      <div className="section">
        <h2 className="section-title">Bed Status per Ward</h2>
        <div className="ward-grid">
          {[1, 2, 3].map(wardId => {
            const wardBeds     = beds.filter(b => b.ward_id === wardId)
            const wardAvail    = wardBeds.filter(b => b.bed_status === 'Available').length
            const wardOccupied = wardBeds.filter(b => b.bed_status === 'Occupied').length
            const wardRate     = wardBeds.length > 0 ? Math.round((wardOccupied / wardBeds.length) * 100) : 0
            return (
              <div className="ward-card" key={wardId}>
                <h3 className="ward-title">Ward {wardId}</h3>
                <div className="ward-stats">
                  <span className="ward-avail">✅ {wardAvail} Available</span>
                  <span className="ward-occ">🔴 {wardOccupied} Occupied</span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${wardRate}%`,
                      background: wardRate > 80 ? '#ef4444' : wardRate > 50 ? '#f59e0b' : '#00c896'
                    }}
                  />
                </div>
                <p className="ward-rate">{wardRate}% occupied</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Waiting List Preview */}
      <div className="section">
        <h2 className="section-title">Waiting List</h2>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Stay ID</th>
                <th>Acuity</th>
                <th>Chief Complaint</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {patients
                .filter(p => p.status === 'waiting')
                .sort((a, b) => a.acuity - b.acuity)
                .slice(0, 10)
                .map(p => (
                  <tr key={p.patient_id}>
                    <td>{p.stay_id}</td>
                    <td>
                      <span className={`acuity-badge acuity-${p.acuity}`}>
                        ESI {p.acuity}
                      </span>
                    </td>
                    <td>{p.chiefcomplaint}</td>
                    <td><span className="status-waiting">Waiting</span></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Dashboard