import { useEffect, useState, useCallback } from 'react'
import { getRecords, reviewRecord, bulkReview } from '../api/emissions'
import { getSources } from '../api/ingestion'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import ScopeBadge from '../components/ScopeBadge'
import {
  CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronUp,
  MessageSquare, Database, Layers
} from 'lucide-react'

const STATUS_META = {
  pending_review: { label: 'Review Queue',  color: 'text-yellow-700', bg: 'bg-yellow-50 border-yellow-200' },
  approved:       { label: 'Approved',       color: 'text-green-700',  bg: 'bg-green-50 border-green-200' },
  rejected:       { label: 'Rejected',       color: 'text-red-700',    bg: 'bg-red-50 border-red-200' },
}

const SOURCE_TYPE_LABEL = { SAP: 'SAP', UTILITY: 'Utility', TRAVEL: 'Travel' }

// ─── Record row component ─────────────────────────────────────────────────────

function FlagBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700">
      <AlertTriangle size={10} /> Flagged
    </span>
  )
}

function RecordRow({ record, onAction, selected, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const [notes, setNotes] = useState('')
  const [acting, setActing] = useState(false)

  const act = async (action, extra = {}) => {
    setActing(true)
    try { await onAction(record.id, { action, notes, ...extra }) }
    finally { setActing(false) }
  }

  const co2 = record.co2e_kg != null ? `${record.co2e_kg.toFixed(2)} kg` : '—'
  const qty = record.raw_quantity != null ? `${record.raw_quantity} ${record.raw_unit}` : '—'
  const normQty = record.normalized_quantity != null
    ? `${record.normalized_quantity.toFixed(2)} ${record.normalized_unit}` : '—'

  return (
    <div className={`border rounded-xl mb-2 overflow-hidden bg-white ${record.is_flagged ? 'border-orange-200' : 'border-gray-200'}`}>
      {/* Summary row */}
      <div className="flex items-start gap-3 px-4 py-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onSelect(record.id)}
          className="mt-1 shrink-0 accent-brand-600"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-0.5">
            <ScopeBadge scope={record.scope} />
            <span className="text-xs text-gray-500 capitalize">{record.category.replace(/_/g, ' ')}</span>
            {record.is_flagged && <FlagBadge />}
          </div>
          <p className="text-sm font-medium text-gray-900 truncate">
            {record.description || record.location || '—'}
          </p>
          <div className="flex gap-3 mt-0.5 text-xs text-gray-500 flex-wrap">
            <span>{record.activity_date || '—'}</span>
            <span>{qty}</span>
            <span className="font-semibold text-gray-800">{co2} CO₂e</span>
          </div>
        </div>

        {/* Quick action buttons — only for pending */}
        <div className="flex items-center gap-1 shrink-0">
          {record.status === 'pending_review' && (
            <>
              <button
                onClick={() => act('approve')} disabled={acting}
                className="p-1.5 rounded-lg text-green-600 hover:bg-green-50 transition-colors" title="Approve"
              ><CheckCircle size={18} /></button>
              <button
                onClick={() => act('reject')} disabled={acting}
                className="p-1.5 rounded-lg text-red-600 hover:bg-red-50 transition-colors" title="Reject"
              ><XCircle size={18} /></button>
            </>
          )}
          {record.status === 'approved' && (
            <button onClick={() => act('reject')} disabled={acting}
              className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 transition-colors" title="Move to rejected"
            ><XCircle size={16} /></button>
          )}
          {record.status === 'rejected' && (
            <button onClick={() => act('approve')} disabled={acting}
              className="p-1.5 rounded-lg text-green-500 hover:bg-green-50 transition-colors" title="Re-approve"
            ><CheckCircle size={16} /></button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-50 transition-colors"
          >
            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 bg-gray-50">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3 text-xs">
            <div><p className="text-gray-400">Raw quantity</p><p className="font-medium">{qty}</p></div>
            <div><p className="text-gray-400">Normalized</p><p className="font-medium">{normQty}</p></div>
            <div>
              <p className="text-gray-400">Emission factor</p>
              <p className="font-medium">
                {record.emission_factor ? `${record.emission_factor} kg/${record.normalized_unit}` : '—'}
              </p>
            </div>
            <div><p className="text-gray-400">Source</p><p className="font-medium">{record.emission_factor_source || '—'}</p></div>
            {record.origin && (
              <div><p className="text-gray-400">Route</p><p className="font-medium">{record.origin} → {record.destination}</p></div>
            )}
            {record.flight_class && (
              <div><p className="text-gray-400">Class</p><p className="font-medium capitalize">{record.flight_class}</p></div>
            )}
            {record.location && (
              <div><p className="text-gray-400">Location</p><p className="font-medium">{record.location}</p></div>
            )}
            {record.vendor && (
              <div><p className="text-gray-400">Vendor</p><p className="font-medium">{record.vendor}</p></div>
            )}
            <div><p className="text-gray-400">Source row #</p><p className="font-medium">{record.source_row_number}</p></div>
            {record.reviewed_by_name && (
              <div>
                <p className="text-gray-400">Reviewed by</p>
                <p className="font-medium">{record.reviewed_by_name}</p>
              </div>
            )}
          </div>

          {/* Flag reasons */}
          {record.flag_reasons?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-orange-700 mb-1">Parser flags:</p>
              {record.flag_reasons.map((r, i) => (
                <div key={i} className="flex items-start gap-1.5 text-xs text-orange-600 mb-1">
                  <AlertTriangle size={11} className="mt-0.5 shrink-0" />{r}
                </div>
              ))}
            </div>
          )}

          {/* Analyst notes */}
          {record.analyst_notes && (
            <div className="mb-3 p-2 bg-blue-50 rounded text-xs text-blue-700">
              <MessageSquare size={11} className="inline mr-1" />{record.analyst_notes}
            </div>
          )}

          {/* Note + actions */}
          <div className="flex gap-2">
            <input
              className="input text-xs flex-1"
              placeholder="Add a note (optional)…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            {record.status === 'pending_review' && (
              <>
                <button onClick={() => act('approve')} disabled={acting} className="btn-primary text-xs px-3">Approve</button>
                <button onClick={() => act('reject')}  disabled={acting} className="btn-danger text-xs px-3">Reject</button>
              </>
            )}
            {record.status === 'approved' && (
              <button onClick={() => act('reject')} disabled={acting} className="btn-danger text-xs px-3">Reject</button>
            )}
            {record.status === 'rejected' && (
              <button onClick={() => act('approve')} disabled={acting} className="btn-primary text-xs px-3">Re-approve</button>
            )}
            <button
              onClick={() => act('add_note')} disabled={acting || !notes}
              className="btn-secondary text-xs px-2" title="Save note"
            ><MessageSquare size={13} /></button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ReviewQueue({ status }) {
  const meta = STATUS_META[status] || STATUS_META.pending_review

  const [sources, setSources] = useState([])          // all datasources
  const [selectedSource, setSelectedSource] = useState(null)  // { id, name, source_type }
  const [records, setRecords] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  // Load all datasources once for the left panel
  useEffect(() => {
    getSources({ page_size: 100 })
      .then((r) => setSources(r.data.results || []))
      .catch(() => {})
  }, [])

  // Load records whenever status or selected source changes
  const load = useCallback(() => {
    setLoading(true)
    setSelected(new Set())
    const params = { status, page_size: 100 }
    if (selectedSource) params.source = selectedSource.id
    getRecords(params)
      .then((r) => { setRecords(r.data.results || []); setCount(r.data.count || 0) })
      .finally(() => setLoading(false))
  }, [status, selectedSource])

  useEffect(() => { load() }, [load])

  // When route changes (status changes), reset selected source
  useEffect(() => { setSelectedSource(null) }, [status])

  const handleAction = async (id, data) => {
    await reviewRecord(id, data)
    load()
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected(selected.size === records.length ? new Set() : new Set(records.map((r) => r.id)))
  }

  const handleBulkAction = async (action) => {
    if (!selected.size) return
    setBulkLoading(true)
    try {
      await bulkReview({ record_ids: [...selected], action })
      setSelected(new Set())
      load()
    } finally {
      setBulkLoading(false)
    }
  }

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">{meta.label}</h1>

      <div className="flex gap-5 items-start">

        {/* ── Left panel: dataset list ─────────────────────────────────── */}
        <div className="w-52 shrink-0">
          <div className="card overflow-hidden">
            {/* All datasets button */}
            <button
              onClick={() => setSelectedSource(null)}
              className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm font-medium transition-colors border-b border-gray-100 ${
                !selectedSource
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Layers size={15} />
              All datasets
            </button>

            {/* Grouped by source type */}
            {['SAP', 'UTILITY', 'TRAVEL'].map((type) => {
              const group = sources.filter((s) => s.source_type === type)
              if (!group.length) return null
              return (
                <div key={type}>
                  <p className="px-3 pt-2 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {SOURCE_TYPE_LABEL[type]}
                  </p>
                  {group.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setSelectedSource(s)}
                      className={`w-full flex items-start gap-2 px-3 py-2 text-left text-sm transition-colors ${
                        selectedSource?.id === s.id
                          ? 'bg-brand-50 text-brand-700 font-medium'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <Database size={13} className="mt-0.5 shrink-0 text-gray-400" />
                      <div className="min-w-0">
                        <p className="truncate text-xs leading-tight">{s.name}</p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {new Date(s.uploaded_at).toLocaleDateString()}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )
            })}

            {sources.length === 0 && (
              <p className="px-3 py-4 text-xs text-gray-400">No datasets yet</p>
            )}
          </div>
        </div>

        {/* ── Right panel: records ────────────────────────────────────── */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div>
              {selectedSource ? (
                <p className="text-sm font-medium text-gray-900">{selectedSource.name}</p>
              ) : (
                <p className="text-sm font-medium text-gray-900">All datasets</p>
              )}
              <p className="text-xs text-gray-500 mt-0.5">{count} records</p>
            </div>

            {/* Bulk actions — only for pending */}
            {selected.size > 0 && status === 'pending_review' && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{selected.size} selected</span>
                <button onClick={() => handleBulkAction('approve')} disabled={bulkLoading} className="btn-primary text-xs px-3">
                  Approve all
                </button>
                <button onClick={() => handleBulkAction('reject')} disabled={bulkLoading} className="btn-danger text-xs px-3">
                  Reject all
                </button>
                <button onClick={() => setSelected(new Set())} className="text-xs text-gray-400 hover:text-gray-600">
                  Clear
                </button>
              </div>
            )}
          </div>

          {/* Select all row */}
          {records.length > 0 && (
            <div className="flex items-center gap-2 mb-2 px-1">
              <input
                type="checkbox"
                className="accent-brand-600"
                checked={selected.size === records.length && records.length > 0}
                onChange={toggleAll}
              />
              <span className="text-xs text-gray-500">Select all {records.length} records</span>
            </div>
          )}

          {/* Records list */}
          {loading ? (
            <div className="card p-12 text-center text-gray-400 text-sm">Loading records…</div>
          ) : records.length === 0 ? (
            <div className="card p-12 text-center">
              {status === 'pending_review' && <CheckCircle size={36} className="text-gray-200 mx-auto mb-3" />}
              {status === 'approved' && <CheckCircle size={36} className="text-green-200 mx-auto mb-3" />}
              {status === 'rejected' && <XCircle size={36} className="text-red-200 mx-auto mb-3" />}
              <p className="text-gray-500 text-sm">
                {selectedSource
                  ? `No ${meta.label.toLowerCase()} records in "${selectedSource.name}"`
                  : `No ${meta.label.toLowerCase()} records yet`}
              </p>
            </div>
          ) : (
            records.map((r) => (
              <RecordRow
                key={r.id}
                record={r}
                onAction={handleAction}
                selected={selected.has(r.id)}
                onSelect={toggleSelect}
              />
            ))
          )}
        </div>
      </div>
    </Layout>
  )
}
