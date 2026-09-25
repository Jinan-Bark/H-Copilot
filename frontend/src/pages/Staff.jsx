import { useEffect, useState } from 'react'
import axios from 'axios'
import { UserPlus, Edit, UserX, UserCheck } from 'lucide-react'
import './Staff.css'

const API = 'http://127.0.0.1:8000'

function Staff() {
  const [nurses, setNurses]       = useState([])
  const [doctors, setDoctors]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [tab, setTab]             = useState('nurses')
  const [filterShift, setFilterShift] = useState('all')
  const [filterGroup, setFilterGroup] = useState('all')
  const [showInactive, setShowInactive] = useState(false)
  const [showForm, setShowForm]   = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [form, setForm] = useState({
    type: 'nurse', ward: '', role: 'RN', shift: 'morning',
    grp: 1, is_intern: false, work_days: 1
  })

  const fetchStaff = async () => {
    try {
      const [n, d] = await Promise.all([
        axios.get(`${API}/nurses?show_inactive=${showInactive}`),
        axios.get(`${API}/doctors?show_inactive=${showInactive}`)
      ])
      setNurses(n.data)
      setDoctors(d.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
  const load = async () => {
    try {
      const [n, d] = await Promise.all([
        axios.get(`${API}/nurses?show_inactive=${showInactive}`),
        axios.get(`${API}/doctors?show_inactive=${showInactive}`)
      ])
      setNurses(n.data)
      setDoctors(d.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }
  load()
}, [showInactive])

  const openAddForm = (type) => {
    setEditTarget(null)
    setForm({ type, ward: '', role: 'RN', shift: 'morning', grp: 1, is_intern: false, work_days: 1 })
    setShowForm(true)
  }

  const openEditForm = (member, type) => {
    setEditTarget({ ...member, type })
    setForm({
      type,
      ward      : member.ward,
      role      : member.role || 'RN',
      shift     : member.shift,
      grp       : member.grp || member.work_days,
      is_intern : member.is_intern || false,
      work_days : member.work_days || 1
    })
    setShowForm(true)
  }

  const handleSubmit = async () => {
    try {
      if (form.type === 'nurse') {
        const payload = { ward: form.ward, role: form.role, shift: form.shift, grp: parseInt(form.grp) }
        if (editTarget) {
          await axios.put(`${API}/nurses/${editTarget.nurse_id}`, payload)
        } else {
          await axios.post(`${API}/nurses`, payload)
        }
      } else {
        const payload = { ward: form.ward, is_intern: form.is_intern === 'true' || form.is_intern === true, shift: form.shift, work_days: parseInt(form.work_days) }
        if (editTarget) {
          await axios.put(`${API}/doctors/${editTarget.doctor_id}`, payload)
        } else {
          await axios.post(`${API}/doctors`, payload)
        }
      }
      setShowForm(false)
      setEditTarget(null)
      fetchStaff()
    } catch (err) {
      console.error(err)
      alert('Error saving staff member.')
    }
  }

  const handleDeactivate = async (member, type) => {
    const id = type === 'nurse' ? member.nurse_id : member.doctor_id
    const endpoint = type === 'nurse' ? 'nurses' : 'doctors'
    try {
      await axios.put(`${API}/${endpoint}/${id}/deactivate`)
      fetchStaff()
    } catch (err) {
      console.error(err)
    }
  }

  const handleReactivate = async (member, type) => {
    const id = type === 'nurse' ? member.nurse_id : member.doctor_id
    const endpoint = type === 'nurse' ? 'nurses' : 'doctors'
    try {
      await axios.put(`${API}/${endpoint}/${id}/reactivate`)
      fetchStaff()
    } catch (err) {
      console.error(err)
    }
  }

  const filteredNurses = nurses.filter(n => {
    const shiftMatch = filterShift === 'all' || n.shift === filterShift
    const groupMatch = filterGroup === 'all' || n.grp === parseInt(filterGroup)
    return shiftMatch && groupMatch
  })

  const filteredDoctors = doctors.filter(d => {
    const shiftMatch = filterShift === 'all' || d.shift === filterShift
    const groupMatch = filterGroup === 'all' || d.work_days === parseInt(filterGroup)
    return shiftMatch && groupMatch
  })

  if (loading) return <div className="loading">Loading...</div>

  return (
    <>
    <div className="staff-page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Staff</h1>
          <p className="page-subtitle">{nurses.length} nurses · {doctors.length} doctors</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn-secondary"
            onClick={() => setShowInactive(!showInactive)}>
            {showInactive ? 'Hide Inactive' : 'Show Inactive'}
          </button>
          <button className="btn-primary" onClick={() => openAddForm(tab === 'nurses' ? 'nurse' : 'doctor')}>
            <UserPlus size={16} />
            Add {tab === 'nurses' ? 'Nurse' : 'Doctor'}
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="staff-summary">
        <div className="summary-card" style={{ borderTopColor: '#00c896' }}>
          <p className="summary-value" style={{ color: '#00c896' }}>{nurses.length}</p>
          <p className="summary-label">Total Nurses</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#0096ff' }}>
          <p className="summary-value" style={{ color: '#0096ff' }}>
            {nurses.filter(n => n.role === 'RN').length}
          </p>
          <p className="summary-label">RNs</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#a855f7' }}>
          <p className="summary-value" style={{ color: '#a855f7' }}>
            {nurses.filter(n => n.role === 'PN').length}
          </p>
          <p className="summary-label">PNs</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#ec4899' }}>
          <p className="summary-value" style={{ color: '#ec4899' }}>
            {nurses.filter(n => n.role === 'Bed_Admission').length}
          </p>
          <p className="summary-label">Bed Admission</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#f59e0b' }}>
          <p className="summary-value" style={{ color: '#f59e0b' }}>{doctors.length}</p>
          <p className="summary-label">Total Doctors</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#10b981' }}>
          <p className="summary-value" style={{ color: '#10b981' }}>
            {doctors.filter(d => !d.is_intern).length}
          </p>
          <p className="summary-label">Doctors</p>
        </div>
        <div className="summary-card" style={{ borderTopColor: '#64748b' }}>
          <p className="summary-value" style={{ color: '#64748b' }}>
            {doctors.filter(d => d.is_intern).length}
          </p>
          <p className="summary-label">Interns</p>
        </div>
      </div>

      {/* Controls */}
      <div className="staff-controls">
        <div className="tab-group">
          <button className={`tab-btn ${tab === 'nurses' ? 'active' : ''}`}
            onClick={() => setTab('nurses')}>
            Nurses ({filteredNurses.length})
          </button>
          <button className={`tab-btn ${tab === 'doctors' ? 'active' : ''}`}
            onClick={() => setTab('doctors')}>
            Doctors ({filteredDoctors.length})
          </button>
        </div>
        <div className="staff-filters">
          <div className="filter-group">
            <label>Shift</label>
            <select value={filterShift} onChange={e => setFilterShift(e.target.value)}>
              <option value="all">All Shifts</option>
              <option value="morning">Morning</option>
              <option value="night">Night</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Group</label>
            <select value={filterGroup} onChange={e => setFilterGroup(e.target.value)}>
              <option value="all">All Groups</option>
              <option value="1">Group 1</option>
              <option value="2">Group 2</option>
            </select>
          </div>
        </div>
      </div>

      {/* Nurses Table */}
      {tab === 'nurses' && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Role</th>
                <th>Ward</th>
                <th>Shift</th>
                <th>Group</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredNurses.map(n => (
                <tr key={n.nurse_id} style={{ opacity: n.is_active ? 1 : 0.5 }}>
                  <td>#{n.nurse_id}</td>
                  <td><span className={`role-badge role-${n.role}`}>{n.role}</span></td>
                  <td>Ward {n.ward}</td>
                  <td><span className="shift-badge">{n.shift}</span></td>
                  <td>Group {n.grp}</td>
                  <td>
                    <span className={`status-badge ${n.is_active ? 'status-admitted' : 'status-discharged'}`}>
                      {n.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn-edit" onClick={() => openEditForm(n, 'nurse')}>
                      <Edit size={13} /> Edit
                    </button>
                    {n.is_active ? (
                      <button className="btn-deactivate" onClick={() => handleDeactivate(n, 'nurse')}>
                        <UserX size={13} /> Deactivate
                      </button>
                    ) : (
                      <button className="btn-reactivate" onClick={() => handleReactivate(n, 'nurse')}>
                        <UserCheck size={13} /> Reactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Doctors Table */}
      {tab === 'doctors' && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Ward</th>
                <th>Shift</th>
                <th>Group</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDoctors.map(d => (
                <tr key={d.doctor_id} style={{ opacity: d.is_active ? 1 : 0.5 }}>
                  <td>#{d.doctor_id}</td>
                  <td>
                    <span className={`role-badge ${d.is_intern ? 'role-intern' : 'role-doctor'}`}>
                      {d.is_intern ? 'Intern' : 'Doctor'}
                    </span>
                  </td>
                  <td>Ward {d.ward}</td>
                  <td><span className="shift-badge">{d.shift}</span></td>
                  <td>Group {d.work_days}</td>
                  <td>
                    <span className={`status-badge ${d.is_active ? 'status-admitted' : 'status-discharged'}`}>
                      {d.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn-edit" onClick={() => openEditForm(d, 'doctor')}>
                      <Edit size={13} /> Edit
                    </button>
                    {d.is_active ? (
                      <button className="btn-deactivate" onClick={() => handleDeactivate(d, 'doctor')}>
                        <UserX size={13} /> Deactivate
                      </button>
                    ) : (
                      <button className="btn-reactivate" onClick={() => handleReactivate(d, 'doctor')}>
                        <UserCheck size={13} /> Reactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>

    {/* Add/Edit Modal */}
    {showForm && (
      <div className="modal-overlay">
        <div className="modal modal-large">
          <h3 className="modal-title">
            {editTarget ? 'Edit' : 'Add'} {form.type === 'nurse' ? 'Nurse' : 'Doctor'}
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
            <div className="form-group">
              <label>Ward</label>
              <input type="text" placeholder="e.g. 1,2,3 or 3"
                value={form.ward}
                onChange={e => setForm({...form, ward: e.target.value})} />
            </div>

            <div className="form-group">
              <label>Shift</label>
              <select value={form.shift} onChange={e => setForm({...form, shift: e.target.value})}>
                <option value="morning">Morning</option>
                <option value="night">Night</option>
              </select>
            </div>

            {form.type === 'nurse' && (
              <>
                <div className="form-group">
                  <label>Role</label>
                  <select value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
                    <option value="RN">RN</option>
                    <option value="PN">PN</option>
                    <option value="Bed_Admission">Bed Admission</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Group</label>
                  <select value={form.grp} onChange={e => setForm({...form, grp: parseInt(e.target.value)})}>
                    <option value={1}>Group 1 — First half</option>
                    <option value={2}>Group 2 — Second half</option>
                  </select>
                </div>
              </>
            )}

            {form.type === 'doctor' && (
              <>
                <div className="form-group">
                  <label>Type</label>
                  <select value={form.is_intern} onChange={e => setForm({...form, is_intern: e.target.value})}>
                    <option value={false}>Doctor</option>
                    <option value={true}>Intern</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Group</label>
                  <select value={form.work_days} onChange={e => setForm({...form, work_days: parseInt(e.target.value)})}>
                    <option value={1}>Group 1 — First half</option>
                    <option value={2}>Group 2 — Second half</option>
                  </select>
                </div>
              </>
            )}
          </div>

          <div className="modal-actions">
            <button className="btn-secondary" onClick={() => { setShowForm(false); setEditTarget(null) }}>
              Cancel
            </button>
            <button className="btn-primary" onClick={handleSubmit}
              disabled={!form.ward}>
              {editTarget ? 'Save Changes' : 'Add Staff'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}

export default Staff