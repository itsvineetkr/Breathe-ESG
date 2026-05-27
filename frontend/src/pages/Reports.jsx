import { useEffect, useState } from 'react'
import { getReports } from '../api/emissions'
import Layout from '../components/Layout'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line, CartesianGrid
} from 'recharts'
import { Download } from 'lucide-react'

const SCOPE_COLORS = { scope_1: '#f97316', scope_2: '#3b82f6', scope_3: '#a855f7' }
const SCOPE_LABELS = { scope_1: 'Scope 1', scope_2: 'Scope 2', scope_3: 'Scope 3' }

function SummaryCard({ label, value, sub }) {
  return (
    <div className="card p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Reports() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getReports().then((r) => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <Layout><div className="py-20 text-center text-gray-400">Loading reports…</div></Layout>
  if (!data) return <Layout><p className="text-gray-500">No data available.</p></Layout>

  // Prepare monthly chart data
  const monthlyData = {}
  ;(data.by_month || []).forEach(({ month, scope, total_co2e_tonnes }) => {
    if (!month) return
    if (!monthlyData[month]) monthlyData[month] = { month }
    monthlyData[month][scope] = total_co2e_tonnes
  })
  const monthlyArr = Object.values(monthlyData).sort((a, b) => a.month.localeCompare(b.month))

  // Pie data for scope breakdown
  const pieData = (data.by_scope || []).map((s) => ({
    name: SCOPE_LABELS[s.scope] || s.scope,
    value: parseFloat(s.total_co2e_tonnes?.toFixed(3) || 0),
    scope: s.scope,
  }))

  const ss = data.status_summary || {}

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Emissions Reports</h1>
          <p className="text-gray-500 text-sm mt-0.5">{data.organization} · Approved records only</p>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <SummaryCard
          label="Total CO₂e"
          value={`${data.total_co2e_tonnes?.toFixed(2) || 0}t`}
          sub="Approved records"
        />
        <SummaryCard
          label="Approved records"
          value={ss.approved || 0}
          sub={`of ${ss.total || 0} total`}
        />
        <SummaryCard
          label="Pending review"
          value={ss.pending_review || 0}
          sub="Not included in totals"
        />
        <SummaryCard
          label="Flagged"
          value={ss.flagged || 0}
          sub="Needs attention"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Scope pie chart */}
        {pieData.length > 0 && (
          <div className="card p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Emissions by Scope</h2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((e) => (
                    <Cell key={e.scope} fill={SCOPE_COLORS[e.scope] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => [`${v.toFixed(3)}t CO₂e`]} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Category bar chart */}
        {data.by_category?.length > 0 && (
          <div className="card p-6">
            <h2 className="font-semibold text-gray-900 mb-4">By Category</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.by_category.map((c) => ({
                name: c.category.replace(/_/g, ' '),
                value: parseFloat(c.total_co2e_tonnes?.toFixed(3) || 0),
                scope: c.scope,
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="t" />
                <Tooltip formatter={(v) => [`${v.toFixed(3)}t CO₂e`]} />
                <Bar dataKey="value" fill="#16a34a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Monthly trend */}
      {monthlyArr.length > 0 && (
        <div className="card p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Monthly Trend (tonnes CO₂e)</h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={monthlyArr}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="t" />
              <Tooltip formatter={(v) => v ? [`${parseFloat(v).toFixed(3)}t`] : ['—']} />
              <Legend />
              {['scope_1', 'scope_2', 'scope_3'].map((s) => (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  name={SCOPE_LABELS[s]}
                  stroke={SCOPE_COLORS[s]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* By dataset */}
      {data.by_source?.length > 0 && (
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">By Dataset</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 text-gray-500 font-medium">Dataset</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Type</th>
                  <th className="text-right py-2 text-gray-500 font-medium">Records</th>
                  <th className="text-right py-2 text-gray-500 font-medium">CO₂e (kg)</th>
                  <th className="text-right py-2 text-gray-500 font-medium">CO₂e (t)</th>
                </tr>
              </thead>
              <tbody>
                {data.by_source.map((s) => (
                  <tr key={s.source__id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 font-medium text-gray-900">{s.source__name}</td>
                    <td className="py-2 text-gray-500">{s.source__source_type}</td>
                    <td className="py-2 text-right text-gray-700">{s.count}</td>
                    <td className="py-2 text-right text-gray-700">{s.total_co2e_kg?.toFixed(1)}</td>
                    <td className="py-2 text-right font-medium text-gray-900">{s.total_co2e_tonnes?.toFixed(3)}t</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Layout>
  )
}
