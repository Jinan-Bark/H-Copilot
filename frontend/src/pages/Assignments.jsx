import { useEffect, useState } from 'react'
import axios from 'axios'
import { Play, RefreshCw } from 'lucide-react'
import './Assignments.css'

const API = 'http://127.0.0.1:8000'

function Assignments() {
  const [assignments, setAssignments] = useState([])
  const [loading, setLoading]         = useState(true)
  const [running, setRunning]         = useState(false)
  const [result, setResult]           = useState(null)
  const [shift, setShift]             = useState('morning')
  const [group, setGroup]             = useState(1)
  const [showTransferModal, setShowTransferModal] = useState(false)
  const [selectedAssignment, setSelectedAssignment] = useState(null)
  const [availableBeds, setAvailableBeds] = useState([])
  const [newBedId, setNewBedId] = useState('')

  const today = new Date().toISOString().split('T')[0]

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/assignments`)
        setAssignments(res.data.sort((a, b) => a.assignment_id - b.assignment_id))
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const runOptimizer = async () => {
    setRunning(true)
    setResult(null)
    try {
      const res = await axios.post(
        `${API}/optimize?shift=${shift}&group=${group}&date_str=${today}`
      )
      setResult(res.data)

      // Reload assignments
      const updated = await axios.get(`${API}/assignments`)
      setAssignments(updated.data.sort((a, b) => a.assignment_id - b.assignment_id))
    } catch (err) {
      console.error(err)
      setResult({ error: 'Optimizer failed. Check backend.' })
    } finally {
      setRunning(false)
    }
  }

  const openTransferModal = async (assignment) => {
    setSelectedAssignment(assignment)
    try {
      const res = await axios.get(`${API}/beds/available`)
      setAvailableBeds(res.data)
    } catch (err) {
      console.error(err)
    }
    setShowTransferModal(true)
  }

  const handleTransfer = async () => {
    try {
      await axios.put(
        `${API}/assignments/${selectedAssignment.assignment_id}/transfer-bed`,
        { new_bed_id: parseInt(newBedId) }
      )
      setShowTransferModal(false)
      setSelectedAssignment(null)
      setNewBedId('')
      const updated = await axios.get(`${API}/assignments`)
      setAssignments(updated.data.sort((a, b) => a.assignment_id - b.assignment_id))
    } catch (err) {
      console.error(err)
      alert('Transfer failed.')
    }
  }

  if (loading) return <div className="loading">Loading...</div>

  return (
    <div className="assignments-page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Assignments</h1>
          <p className="page-subtitle">Run the optimizer to assign patients to beds and staff</p>
        </div>
      </div>

      {/* Optimizer Panel */}
      <div className="optimizer-panel">
        <h3 className="panel-title">🧠 OR Optimizer</h3>
        <p className="panel-desc">
          Select the shift and group, then run the optimizer to automatically
          assign all waiting patients to available beds, nurses, and doctors.
        </p>
        <div className="optimizer-controls">
          <div className="filter-group">
            <label>Shift</label>
            <select value={shift} onChange={e => setShift(e.target.value)}>
              <option value="morning">Morning</option>
              <option value="night">Night</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Group</label>
            <select value={group} onChange={e => setGroup(parseInt(e.target.value))}>
              <option value={1}>Group 1 — First half of week</option>
              <option value={2}>Group 2 — Second half of week</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Date</label>
            <input type="text" readOnly value={today}
              style={{ color: '#64748b', cursor: 'not-allowed',
                background: '#0d1520', border: '1px solid #1e2d3d',
                borderRadius: '8px', padding: '8px 14px' }} />
          </div>
          <button
            className="btn-optimize"
            onClick={runOptimizer}
            disabled={running}>
            {running
              ? <><RefreshCw size={16} className="spin" /> Running...</>
              : <><Play size={16} /> Run Optimizer</>}
          </button>
        </div>

        {/* Result Summary */}
        {result && !result.error && (
          <div className="result-summary">
            <div className="result-card success">
              <p className="result-value">{result.assigned}</p>
              <p className="result-label">Patients Assigned</p>
            </div>
            <div className="result-card warning">
              <p className="result-value">{result.waiting}</p>
              <p className="result-label">Still Waiting</p>
            </div>
          </div>
        )}

        {result?.error && (
          <div className="error-banner">{result.error}</div>
        )}
      </div>

      {/* Assignments Table */}
      <div className="section">
        <h2 className="section-title">Current Assignments</h2>
        {assignments.length === 0 ? (
          <div className="empty-state">
            No assignments yet. Run the optimizer to generate assignments.
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Stay ID</th>
                  <th>Acuity</th>
                  <th>Chief Complaint</th>
                  <th>Bed</th>
                  <th>RN</th>
                  <th>PN</th>
                  <th>Doctor</th>
                  <th>Shift</th>
                  <th>Date</th>
                  <th>Assigned At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map(a => (
                  <tr key={a.assignment_id}>
                    <td>#{assignments.indexOf(a) + 1}</td>
                    <td>
                      {a.stay_id}
                      {(() => {
                        const assignedTime = new Date(a.assigned_at + 'Z') // Ensure it's treated as UTC
                        const now = new Date()
                        const diffMinutes = (now - assignedTime) / 1000 / 60
                        return diffMinutes <= 10
                      })() && (
                        <span className="new-badge">New</span>
                      )}
                    </td>
                    <td>
                      <span className={`acuity-badge acuity-${a.acuity}`}>
                        ESI {a.acuity}
                      </span>
                    </td>
                    <td>{a.chiefcomplaint}</td>
                    <td>Bed {a.bed_number} — Ward {a.ward_id}</td>
                    <td>RN #{a.rn_id}</td>
                    <td>PN #{a.pn_id}</td>
                    <td>{a.is_intern ? 'Intern' : 'Doctor'} #{a.doctor_id}</td>
                    <td><span className="shift-badge">{a.shift}</span></td>
                    <td>{a.date}</td>
                    <td className="date-cell">
                      {new Date(a.assigned_at).toLocaleString()}
                    </td>
                    <td>
                      <button
                        className="btn-transfer"
                        onClick={() => openTransferModal(a)}>
                        Transfer Bed
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {/* Transfer Bed Modal */}
      {showTransferModal && selectedAssignment && (
        <div className="modal-overlay">
          <div className="modal">
            <h3 className="modal-title">Transfer Bed</h3>
            <p className="modal-text">
              Patient Stay ID: {selectedAssignment.stay_id} — 
              Currently in Bed {selectedAssignment.bed_number} Ward {selectedAssignment.ward_id}
            </p>
            <div className="form-group" style={{ marginBottom: '24px' }}>
              <label>Select New Bed *</label>
              <select value={newBedId} onChange={e => setNewBedId(e.target.value)}
                style={{ background:'#0d1520', border:'1px solid #1e2d3d',
                  borderRadius:'8px', padding:'8px 14px', color:'#e2e8f0',
                  fontSize:'0.875rem', width:'100%', outline:'none' }}>
                <option value="">Select Available Bed</option>
                {availableBeds.map(b => (
                  <option key={b.bed_id} value={b.bed_id}>
                    Bed {b.bed_number} — Ward {b.ward_id}
                  </option>
                ))}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary"
                onClick={() => { setShowTransferModal(false); setSelectedAssignment(null) }}>
                Cancel
              </button>
              <button className="btn-primary"
                onClick={handleTransfer}
                disabled={!newBedId}>
                Confirm Transfer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Assignments