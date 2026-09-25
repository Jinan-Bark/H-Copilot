import { useEffect, useState } from 'react'
import axios from 'axios'
import { UserPlus, LogOut } from 'lucide-react'
import './Patients.css'

const API = 'http://127.0.0.1:8000'

function Patients() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading]   = useState(true)
  const [filter, setFilter]     = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [toast, setToast]       = useState(null)
  const [confirmDischarge, setConfirmDischarge] = useState(null) // holds patient_id
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [availableBeds, setAvailableBeds]     = useState([])
  const [allNurses, setAllNurses]             = useState([])
  const [allDoctors, setAllDoctors]           = useState([])
  const [manualForm, setManualForm] = useState({
  bed_id: '', rn_id: '', pn_id: '', doctor_id: '', shift: 'morning', group: 1
  })
  const [form, setForm]         = useState({
    acuity: '', chiefcomplaint: '',
    temperature: '', heartrate: '', resprate: '',
    o2sat: '', sbp: '', dbp: '', pain: ''
  })

  const fetchPatients = async () => {
    try {
      const res = await axios.get(`${API}/patients`)
      setPatients(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const load = async () => {
        try {
        const res = await axios.get(`${API}/patients`)
        setPatients(res.data)
        } catch (err) {
        console.error(err)
        } finally {
        setLoading(false)
        }
    }
    load()
    }, [])

  const handleDischarge = async () => {
    try {
      const res = await axios.put(`${API}/patients/${confirmDischarge}/discharge`)
      setConfirmDischarge(null)
      fetchPatients()
      if (res.data.newly_assigned && res.data.newly_assigned.length > 0) {
        setToast(`✅ ${res.data.newly_assigned.length} patient(s) auto-assigned: Stay IDs ${res.data.newly_assigned.join(', ')}`)
        setTimeout(() => setToast(null), 5000)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const openAssignModal = async (patient) => {
    setSelectedPatient(patient)
    try {
      const [b, w] = await Promise.all([
        axios.get(`${API}/beds/available`),
        axios.get(`${API}/staff/workload`)
      ])
      setAvailableBeds(b.data)
      setAllNurses(w.data.nurses)
      setAllDoctors(w.data.doctors)
    } catch (err) {
      console.error(err)
    }
    setShowAssignModal(true)
  }

  const handleManualAssign = async () => {
    try {
      await axios.post(`${API}/assign-manual`, {
        patient_id : selectedPatient.patient_id,
        bed_id     : parseInt(manualForm.bed_id),
        rn_id      : parseInt(manualForm.rn_id),
        pn_id      : parseInt(manualForm.pn_id),
        doctor_id  : parseInt(manualForm.doctor_id),
        shift      : manualForm.shift,
        date_str   : new Date().toISOString().split('T')[0]
      })
      setShowAssignModal(false)
      setSelectedPatient(null)
      setManualForm({ bed_id:'', rn_id:'', pn_id:'', doctor_id:'', shift:'morning' })
      fetchPatients()
    } catch (err) {
      console.error(err)
      alert('Assignment failed. Check all fields.')
    }
  }

  const handleAddPatient = async (e) => {
    e.preventDefault()
    try {
      await axios.post(`${API}/patients`, {
        acuity         : parseInt(form.acuity),
        chiefcomplaint : form.chiefcomplaint,
        temperature    : form.temperature    ? parseFloat(form.temperature)  : null,
        heartrate      : form.heartrate      ? parseInt(form.heartrate)      : null,
        resprate       : form.resprate       ? parseInt(form.resprate)       : null,
        o2sat          : form.o2sat          ? parseFloat(form.o2sat)        : null,
        sbp            : form.sbp            ? parseInt(form.sbp)            : null,
        dbp            : form.dbp            ? parseInt(form.dbp)            : null,
        pain           : form.pain           ? parseInt(form.pain)           : null,
      })
      setShowForm(false)
      setForm({ stay_id:'', acuity:'', chiefcomplaint:'',
        temperature:'', heartrate:'', resprate:'',
        o2sat:'', sbp:'', dbp:'', pain:'' })
      fetchPatients()
    } catch (err) {
      console.error(err)
      alert('Error adding patient. Check stay_id is unique.')
    }
  }

  const filtered = patients.filter(p => {
    if (filter === 'all')        return true
    if (filter === 'waiting')    return p.status === 'waiting'
    if (filter === 'admitted')   return p.status === 'admitted'
    if (filter === 'discharged') return p.status === 'discharged'
    return true
  }).sort((a, b) => a.acuity - b.acuity)

  if (loading) return <div className="loading">Loading...</div>

  return (
    <>
    <div className="patients-page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Patients</h1>
          <p className="page-subtitle">{patients.length} total patients in the system</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <UserPlus size={16} />
          Add Patient
        </button>
      </div>

      {/* Add Patient Form */}
      {showForm && (
        <div className="form-card">
          <h3 className="form-title">New Patient</h3>
          <form onSubmit={handleAddPatient}>
            <div className="form-grid">
              <div className="form-group">
                <label>Acuity (ESI 1-5) *</label>
                <select required value={form.acuity}
                  onChange={e => setForm({...form, acuity: e.target.value})}>
                  <option value="">Select</option>
                  <option value="1">ESI 1 — Immediate</option>
                  <option value="2">ESI 2 — Emergent</option>
                  <option value="3">ESI 3 — Urgent</option>
                  <option value="4">ESI 4 — Less Urgent</option>
                  <option value="5">ESI 5 — Non Urgent</option>
                </select>
              </div>
              <div className="form-group">
                <label>Arrival Time (Auto)</label>
                <input 
                    type="text" 
                    readOnly 
                    value={new Date().toLocaleString()} 
                    style={{ color: '#64748b', cursor: 'not-allowed' }}
                />
               </div>
              <div className="form-group form-full">
                <label>Chief Complaint *</label>
                <input type="text" required value={form.chiefcomplaint}
                  onChange={e => setForm({...form, chiefcomplaint: e.target.value})} />
              </div>
              <div className="form-group">
                <label>Temperature</label>
                <input type="number" step="0.1" value={form.temperature}
                  onChange={e => setForm({...form, temperature: e.target.value})} />
              </div>
              <div className="form-group">
                <label>Heart Rate</label>
                <input type="number" value={form.heartrate}
                  onChange={e => setForm({...form, heartrate: e.target.value})} />
              </div>
              <div className="form-group">
                <label>Resp Rate</label>
                <input type="number" value={form.resprate}
                  onChange={e => setForm({...form, resprate: e.target.value})} />
              </div>
              <div className="form-group">
                <label>O2 Sat</label>
                <input type="number" step="0.1" value={form.o2sat}
                  onChange={e => setForm({...form, o2sat: e.target.value})} />
              </div>
              <div className="form-group">
                <label>SBP</label>
                <input type="number" value={form.sbp}
                  onChange={e => setForm({...form, sbp: e.target.value})} />
              </div>
              <div className="form-group">
                <label>DBP</label>
                <input type="number" value={form.dbp}
                  onChange={e => setForm({...form, dbp: e.target.value})} />
              </div>
              <div className="form-group">
                <label>Pain (0-10)</label>
                <input type="number" min="0" max="10" value={form.pain}
                  onChange={e => setForm({...form, pain: e.target.value})} />
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="btn-secondary"
                onClick={() => setShowForm(false)}>Cancel</button>
              <button type="submit" className="btn-primary">Add Patient</button>
            </div>
          </form>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="filter-tabs">
        {['all','waiting','admitted','discharged'].map(f => (
          <button key={f}
            className={`filter-tab ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
            <span className="tab-count">
              {f === 'all' ? patients.length
                : patients.filter(p => p.status === f).length}
            </span>
          </button>
        ))}
      </div>

      {/* Patients Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Stay ID</th>
              <th>Acuity</th>
              <th>Chief Complaint</th>
              <th>Vitals</th>
              <th>Status</th>
              <th>Arrival</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(p => (
              <tr key={p.patient_id}>
                <td>#{p.patient_id}</td>
                <td>{p.stay_id}</td>
                <td>
                  <span className={`acuity-badge acuity-${p.acuity}`}>
                    ESI {p.acuity}
                  </span>
                </td>
                <td>{p.chiefcomplaint}</td>
                <td className="vitals-cell">
                  {p.heartrate && <span>HR: {p.heartrate}</span>}
                  {p.o2sat     && <span>O2: {p.o2sat}%</span>}
                  {p.sbp       && <span>BP: {p.sbp}/{p.dbp}</span>}
                </td>
                <td>
                  <span className={`status-badge status-${p.status}`}>
                    {p.status}
                  </span>
                </td>
                <td className="date-cell">
                  {p.arrival_time
                    ? new Date(p.arrival_time).toLocaleString()
                    : '—'}
                </td>
                <td>
                  {p.status === 'waiting' && (
                    <button
                      className="btn-assign"
                      onClick={() => openAssignModal(p)}>
                      Assign
                    </button>
                  )}
                  {p.status === 'admitted' && (
                    <button
                      className="btn-discharge"
                      onClick={() => setConfirmDischarge(p.patient_id)}>
                      <LogOut size={14} />
                      Discharge
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
      {/* Discharge Confirmation Modal */}
      {confirmDischarge && (
        <div className="modal-overlay">
          <div className="modal">
            <h3 className="modal-title">Discharge Patient</h3>
            <p className="modal-text">
              Are you sure you want to discharge this patient?
              Their bed will be marked as available.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary"
                onClick={() => setConfirmDischarge(null)}>
                Cancel
              </button>
              <button className="btn-danger"
                onClick={handleDischarge}>
                Confirm Discharge
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Manual Assignment Modal */}
      {showAssignModal && selectedPatient && (
        <div className="modal-overlay">
          <div className="modal modal-large">
            <h3 className="modal-title">
              Manual Assignment — {selectedPatient.chiefcomplaint}
            </h3>
            <p className="modal-text">
              ESI {selectedPatient.acuity} · Stay ID: {selectedPatient.stay_id}
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px', width: '100%' }}>
              <div className="form-group">
                <label>Available Bed *</label>
                <select value={manualForm.bed_id}
                  onChange={e => setManualForm({...manualForm, bed_id: e.target.value})}>
                  <option value="">Select Bed</option>
                  {availableBeds.map(b => (
                    <option key={b.bed_id} value={b.bed_id}>
                      Bed {b.bed_number} — Ward {b.ward_id}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Shift *</label>
                <select value={manualForm.shift}
                  onChange={e => setManualForm({...manualForm, shift: e.target.value, rn_id:'', pn_id:'', doctor_id:''})}>
                  <option value="morning">Morning</option>
                  <option value="night">Night</option>
                </select>
              </div>

              <div className="form-group">
                <label>Group *</label>
                <select value={manualForm.group}
                  onChange={e => setManualForm({...manualForm, 
                    group: parseInt(e.target.value), 
                    rn_id:'', pn_id:'', doctor_id:''})}>
                  <option value={1}>Group 1 — First half of week</option>
                  <option value={2}>Group 2 — Second half of week</option>
                </select>
              </div>             

              <div className="form-group">
                <label>RN *</label>
                <select value={manualForm.rn_id}
                  onChange={e => setManualForm({...manualForm, rn_id: e.target.value})}>
                  <option value="">Select RN</option>
                  {allNurses.filter(n => n.role === 'RN' && n.shift === manualForm.shift && n.grp === manualForm.group).map(n => (
                    <option key={n.nurse_id} value={n.nurse_id}>
                      RN #{n.nurse_id} — Ward {n.ward} ({n.patients} patients)
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>PN *</label>
                <select value={manualForm.pn_id}
                  onChange={e => setManualForm({...manualForm, pn_id: e.target.value})}>
                  <option value="">Select PN</option>
                  {allNurses.filter(n => n.role === 'PN' && n.shift === manualForm.shift && n.grp === manualForm.group).map(n => (
                    <option key={n.nurse_id} value={n.nurse_id}>
                      PN #{n.nurse_id} — Ward {n.ward} ({n.patients} patients)
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Doctor / Intern *</label>
                <select value={manualForm.doctor_id}
                  onChange={e => setManualForm({...manualForm, doctor_id: e.target.value})}>
                  <option value="">Select Doctor</option>
                  {allDoctors.filter(d => d.shift === manualForm.shift && d.work_days === parseInt(manualForm.group)).map(d => (
                    <option key={d.doctor_id} value={d.doctor_id}>
                      {d.is_intern ? 'Intern' : 'Doctor'} #{d.doctor_id} — Ward {d.ward} ({d.patients} patients)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn-secondary"
                onClick={() => { setShowAssignModal(false); setSelectedPatient(null) }}>
                Cancel
              </button>
              <button className="btn-primary"
                onClick={handleManualAssign}
                disabled={!manualForm.bed_id || !manualForm.rn_id || !manualForm.pn_id || !manualForm.doctor_id}>
                Confirm Assignment
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Toast Notification */}
      {toast && (
        <div className="toast">
          {toast}
        </div>
      )}
    </>
  )
}

export default Patients