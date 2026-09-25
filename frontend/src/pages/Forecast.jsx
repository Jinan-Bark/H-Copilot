import { useEffect, useState } from 'react'
import axios from 'axios'
import { TrendingUp, Users } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import './Forecast.css'

const API = 'http://127.0.0.1:8000'

function Forecast() {
  const [weekData, setWeekData] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDay, setSelectedDay] = useState(null)

  useEffect(() => {
    const fetchForecast = async () => {
      try {
        const today = new Date().toISOString().split('T')[0]
        const res = await axios.get(`${API}/forecast/week`, { params: { start_date: today } })
        setWeekData(res.data)
        setSelectedDay(res.data[0])
      } catch (err) {
        console.error('Error fetching forecast:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchForecast()
  }, [])

  if (loading) return <div className="loading">Loading forecast...</div>

  const chartData = weekData.map(day => ({
    date: day.date.slice(5),
    predicted: Math.round(day.daily_total_predicted)
  }))

  return (
    <div className="forecast">
      <div className="page-header">
        <h1 className="page-title">Flow Forecast</h1>
        <p className="page-subtitle">Predicted ED Arrivals — Next 7 Days</p>
      </div>

      <div className="section">
        <h2 className="section-title">Weekly Overview</h2>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData}>
              <XAxis dataKey="date" stroke="#8892a6" />
              <YAxis stroke="#8892a6" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1a2332', border: 'none', borderRadius: '8px', color: '#fff' }}
              />
              <Bar dataKey="predicted" fill="#0096ff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="section">
        <h2 className="section-title">Daily Breakdown</h2>
        <div className="day-tabs">
          {weekData.map(day => (
            <button
              key={day.date}
              className={`day-tab ${selectedDay?.date === day.date ? 'active' : ''}`}
              onClick={() => setSelectedDay(day)}
            >
              <span className="day-tab-date">{day.date.slice(5)}</span>
              <span className="day-tab-total">{Math.round(day.daily_total_predicted)}</span>
            </button>
          ))}
        </div>

        {selectedDay && (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time Slot</th>
                  <th>Predicted Arrivals</th>
                  <th>Staffing Buffer</th>
                </tr>
              </thead>
              <tbody>
                {selectedDay.slots.map(slot => (
                  <tr key={slot.hour_slot}>
                    <td>{slotLabel(slot.hour_slot)}</td>
                    <td>
                      <span className="predicted-value">
                        <Users size={14} /> {Math.round(slot.predicted_arrivals)}
                      </span>
                    </td>
                    <td>
                      <span className="buffer-value">
                        <TrendingUp size={14} /> {Math.round(slot.recommended_staffing_buffer)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function slotLabel(hourSlot) {
  const labels = ['00:00 - 04:00', '04:00 - 08:00', '08:00 - 12:00', '12:00 - 16:00', '16:00 - 20:00', '20:00 - 24:00']
  return labels[hourSlot]
}

export default Forecast