import { useEffect, useState } from 'react'
import { getAuditLogs } from '../api/emissions'
import Layout from '../components/Layout'
import { ScrollText, Filter } from 'lucide-react'

const ACTION_COLORS = {
  upload: 'bg-blue-100 text-blue-700',
  parse_complete: 'bg-blue-100 text-blue-700',
  approve: 'bg-green-100 text-green-700',
  reject: 'bg-red-100 text-red-700',
  flag: 'bg-orange-100 text-orange-700',
  unflag: 'bg-gray-100 text-gray-700',
  add_note: 'bg-purple-100 text-purple-700',
  scope_change: 'bg-yellow-100 text-yellow-700',
  edit: 'bg-yellow-100 text-yellow-700',
}

export default function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [actionFilter, setActionFilter] = useState('')

  const load = () => {
    setLoading(true)
    const params = {}
    if (actionFilter) params.action = actionFilter
    getAuditLogs(params)
      .then((r) => { setLogs(r.data.results || []); setCount(r.data.count || 0) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [actionFilter])

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
          <p className="text-gray-500 text-sm mt-0.5">{count} total events</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-gray-400" />
          <select
            className="input w-44 text-sm"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          >
            <option value="">All actions</option>
            <option value="upload">Upload</option>
            <option value="approve">Approve</option>
            <option value="reject">Reject</option>
            <option value="flag">Flag</option>
            <option value="add_note">Note</option>
            <option value="scope_change">Scope change</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-gray-400">Loading…</div>
      ) : logs.length === 0 ? (
        <div className="card p-12 text-center">
          <ScrollText size={40} className="text-gray-200 mx-auto mb-3" />
          <p className="text-gray-500">No audit events yet.</p>
        </div>
      ) : (
        <div className="card divide-y divide-gray-50">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-4 px-5 py-4 hover:bg-gray-50">
              <span className={`inline-block mt-0.5 px-2 py-0.5 rounded text-xs font-medium shrink-0 ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-700'}`}>
                {log.action_display}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900">
                  <span className="font-medium">{log.user_name}</span>
                  {log.datasource_name && <span className="text-gray-500"> · {log.datasource_name}</span>}
                </p>
                {log.notes && <p className="text-xs text-gray-500 mt-0.5 italic">"{log.notes}"</p>}
                {log.new_values && Object.keys(log.new_values).length > 0 && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {Object.entries(log.new_values).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(' · ')}
                  </p>
                )}
              </div>
              <time className="text-xs text-gray-400 shrink-0">
                {new Date(log.timestamp).toLocaleString()}
              </time>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
