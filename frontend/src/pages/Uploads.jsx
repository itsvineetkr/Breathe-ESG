import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getSources, getSourceDetail } from '../api/ingestion'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import { Database, AlertTriangle, ChevronRight } from 'lucide-react'

const SOURCE_LABELS = { SAP: 'SAP Flat File', UTILITY: 'Utility Portal CSV', TRAVEL: 'Travel Platform CSV' }

export default function Uploads() {
  const { type } = useParams() // 'sap' | 'utility' | 'travel'
  const sourceType = type?.toUpperCase()
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    setLoading(true)
    getSources({ source_type: sourceType })
      .then((r) => setSources(r.data.results || []))
      .finally(() => setLoading(false))
  }, [sourceType])

  const loadDetail = async (s) => {
    setSelected(s)
    const r = await getSourceDetail(s.id)
    setDetail(r.data)
  }

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{SOURCE_LABELS[sourceType] || 'Uploads'}</h1>
      <p className="text-gray-500 mb-6">All {sourceType} datasets uploaded by your organization.</p>

      {loading ? (
        <div className="card p-12 text-center text-gray-400">Loading…</div>
      ) : sources.length === 0 ? (
        <div className="card p-12 text-center">
          <Database size={40} className="text-gray-200 mx-auto mb-3" />
          <p className="text-gray-500">No {sourceType} datasets uploaded yet.</p>
          <Link to="/upload" className="btn-primary mt-4 inline-flex">Upload Dataset</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* List */}
          <div className="space-y-2">
            {sources.map((s) => (
              <button
                key={s.id}
                onClick={() => loadDetail(s)}
                className={`w-full text-left card p-4 hover:shadow-md transition-shadow ${selected?.id === s.id ? 'ring-2 ring-brand-500' : ''}`}
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <p className="font-medium text-gray-900 truncate">{s.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {s.original_filename} · {new Date(s.uploaded_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-gray-500">
                      {s.parsed_rows} rows · by {s.uploaded_by_name}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 ml-3 shrink-0">
                    <StatusBadge status={s.status} />
                    {s.flagged_rows > 0 && (
                      <span className="flex items-center gap-1 text-xs text-orange-600">
                        <AlertTriangle size={11} />
                        {s.flagged_rows} flagged
                      </span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Detail panel */}
          {detail && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-3">{detail.name}</h3>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  ['Total rows', detail.total_rows],
                  ['Parsed', detail.parsed_rows],
                  ['Flagged', detail.flagged_rows],
                  ['Failed', detail.failed_rows],
                ].map(([l, v]) => (
                  <div key={l} className="bg-gray-50 rounded-lg p-3">
                    <p className="text-lg font-bold text-gray-900">{v}</p>
                    <p className="text-xs text-gray-500">{l}</p>
                  </div>
                ))}
              </div>

              {detail.parse_log?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Parse Errors</h4>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {detail.parse_log.map((e, i) => (
                      <div key={i} className="text-xs p-2 bg-red-50 rounded text-red-700">
                        Row {e.row}: {e.error}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Link
                to={`/review?source=${detail.id}`}
                className="btn-secondary mt-4 text-sm inline-flex items-center gap-1"
              >
                View records <ChevronRight size={14} />
              </Link>
            </div>
          )}
        </div>
      )}
    </Layout>
  )
}
