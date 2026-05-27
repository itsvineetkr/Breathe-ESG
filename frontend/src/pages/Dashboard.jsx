import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getReports } from '../api/emissions'
import { getSources } from '../api/ingestion'
import { useAuth } from '../context/AuthContext'
import Layout from '../components/Layout'
import { Leaf, AlertTriangle, CheckCircle, Clock, XCircle, TrendingUp } from 'lucide-react'

function StatCard({ label, value, icon: Icon, color, to }) {
  const inner = (
    <div className="card p-5 flex items-center gap-4 hover:shadow-md transition-shadow">
      <div className={`p-3 rounded-xl ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
  return to ? <Link to={to}>{inner}</Link> : inner
}

export default function Dashboard() {
  const { user } = useAuth()
  const [report, setReport] = useState(null)
  const [recentSources, setRecentSources] = useState([])

  useEffect(() => {
    getReports().then((r) => setReport(r.data)).catch(() => {})
    getSources({ page_size: 5 }).then((r) => setRecentSources(r.data.results || [])).catch(() => {})
  }, [])

  const summary = report?.status_summary || {}
  const totalCO2 = report?.total_co2e_tonnes?.toFixed(2) || '—'

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {user?.first_name || user?.email}
        </h1>
        <p className="text-gray-500 mt-1">{user?.organization?.name} · {user?.role}</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total CO₂e (approved)"
          value={`${totalCO2}t`}
          icon={Leaf}
          color="bg-brand-600"
        />
        <StatCard
          label="Pending review"
          value={summary.pending_review ?? '—'}
          icon={Clock}
          color="bg-yellow-500"
          to="/review"
        />
        <StatCard
          label="Approved records"
          value={summary.approved ?? '—'}
          icon={CheckCircle}
          color="bg-green-600"
          to="/approved"
        />
        <StatCard
          label="Flagged"
          value={summary.flagged ?? '—'}
          icon={AlertTriangle}
          color="bg-orange-500"
          to="/review?is_flagged=true"
        />
      </div>

      {/* Scope breakdown */}
      {report?.by_scope && report.by_scope.length > 0 && (
        <div className="card p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp size={18} className="text-brand-600" />
            Emissions by Scope (approved)
          </h2>
          <div className="space-y-3">
            {report.by_scope.map((s) => {
              const label = { scope_1: 'Scope 1 — Direct', scope_2: 'Scope 2 — Electricity', scope_3: 'Scope 3 — Travel' }[s.scope] || s.scope
              const color = { scope_1: 'bg-orange-500', scope_2: 'bg-blue-500', scope_3: 'bg-purple-500' }[s.scope] || 'bg-gray-400'
              const pct = report.total_co2e_kg > 0 ? ((s.total_co2e_kg / report.total_co2e_kg) * 100).toFixed(0) : 0
              return (
                <div key={s.scope}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-gray-700">{label}</span>
                    <span className="text-gray-500">{s.total_co2e_tonnes?.toFixed(2)}t CO₂e ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full">
                    <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent uploads */}
      {recentSources.length > 0 && (
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Recent Uploads</h2>
          <div className="space-y-2">
            {recentSources.map((s) => (
              <div key={s.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{s.name}</p>
                  <p className="text-xs text-gray-500">
                    {s.source_type_display} · {s.parsed_rows} rows · {new Date(s.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {s.flagged_rows > 0 && (
                    <span className="text-xs text-orange-600 font-medium">{s.flagged_rows} flagged</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    s.status === 'completed' ? 'bg-green-100 text-green-700' :
                    s.status === 'failed' ? 'bg-red-100 text-red-700' :
                    'bg-blue-100 text-blue-700'
                  }`}>{s.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!report && (
        <div className="card p-12 text-center">
          <Leaf size={40} className="text-gray-200 mx-auto mb-3" />
          <p className="text-gray-500">No data yet. Upload your first dataset to get started.</p>
          {user?.role === 'admin' && (
            <Link to="/upload" className="btn-primary mt-4 inline-flex">Upload Data</Link>
          )}
        </div>
      )}
    </Layout>
  )
}
