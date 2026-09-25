import { useEffect, useState } from 'react'
import axios from 'axios'
import './Beds.css'

const API = 'http://127.0.0.1:8000'

const statusColor = {
  Available:   { bg: 'rgba(0,200,150,0.1)',   border: '#00c896', text: '#00c896'  },
  Occupied:    { bg: 'rgba(239,68,68,0.1)',    border: '#ef4444', text: '#fca5a5'  },
  Maintenance: { bg: 'rgba(234,179,8,0.1)',    border: '#f59e0b', text: '#fde047'  },
}

function Beds() {
  const [beds, setBeds]     = useState([])
  const [loading, setLoading] = useState(true)
  const [filterWard, setFilterWard] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/beds`)
        setBeds(res.data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = beds.filter(b => {
    const wardMatch   = filterWard   === 'all' || b.ward_id === parseInt(filterWard)
    const statusMatch = filterStatus === 'all' || b.bed_status === filterStatus
    return wardMatch && statusMatch
  })

  const available   = beds.filter(b => b.bed_status === 'Available').length
  const occupied    = beds.filter(b => b.bed_status === 'Occupied').length
  const maintenance = beds.filter(b => b.bed_status === 'Maintenance').length

  if (loading) return <div className="loading">Loading...</div>

  return (
    <div className="beds-page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Beds</h1>
          <p className="page-subtitle">{beds.length} total beds across 3 wards</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="beds-summary">
        <div className="summary-card" style={{ borderTopColor: '#00c896' }}>
          <p className="summary-value" style={{ color: '#00c896' }}>{available}</p>
          <p className="summary-label">Available</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#ef4444' }}>
          <p className="summary-value" style={{ color: '#ef4444' }}>{occupied}</p>
          <p className="summary-label">Occupied</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#f59e0b' }}>
          <p className="summary-value" style={{ color: '#f59e0b' }}>{maintenance}</p>
          <p className="summary-label">Maintenance</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#0096ff' }}>
          <p className="summary-value" style={{ color: '#0096ff' }}>{beds.length}</p>
          <p className="summary-label">Total</p>
        </div>
      </div>

      {/* Filters */}
      <div className="beds-filters">
        <div className="filter-group">
          <label>Ward</label>
          <select value={filterWard} onChange={e => setFilterWard(e.target.value)}>
            <option value="all">All Wards</option>
            <option value="1">Ward 1</option>
            <option value="2">Ward 2</option>
            <option value="3">Ward 3</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Status</label>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
            <option value="all">All Status</option>
            <option value="Available">Available</option>
            <option value="Occupied">Occupied</option>
            <option value="Maintenance">Maintenance</option>
          </select>
        </div>
      </div>

      {/* Beds Grid */}
      {[1, 2, 3].map(wardId => {
        const wardBeds = filtered.filter(b => b.ward_id === wardId)
        if (wardBeds.length === 0) return null
        return (
          <div key={wardId} className="ward-section">
            <h2 className="ward-heading">Ward {wardId}</h2>
            <div className="beds-grid">
              {wardBeds.map(bed => {
                const style = statusColor[bed.bed_status] || statusColor['Available']
                return (
                  <div key={bed.bed_id} className="bed-card"
                    style={{ background: style.bg, borderColor: style.border }}>
                    <div className="bed-number">Bed {bed.bed_number}</div>
                    <div className="bed-status" style={{ color: style.text }}>
                      {bed.bed_status}
                    </div>
                    <div className="bed-ward">Ward {bed.ward_id}</div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default Beds