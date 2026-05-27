import { useEffect, useState } from 'react'
import { getAnalysts, addAnalyst, removeAnalyst } from '../api/auth'
import Layout from '../components/Layout'
import { Users, Plus, Trash2, Shield, UserCheck } from 'lucide-react'

export default function Team() {
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)

  const load = () => {
    setLoading(true)
    getAnalysts().then((r) => setMembers(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const handleAdd = async (e) => {
    e.preventDefault()
    setError('')
    setAdding(true)
    try {
      await addAnalyst(form)
      setShowAdd(false)
      setForm({ first_name: '', last_name: '', email: '', password: '' })
      load()
    } catch (err) {
      const d = err.response?.data
      setError(d && typeof d === 'object'
        ? Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join('\n')
        : 'Failed to add analyst.')
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (id, name) => {
    if (!confirm(`Deactivate ${name}?`)) return
    await removeAnalyst(id)
    load()
  }

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Team</h1>
          <p className="text-gray-500 text-sm mt-0.5">Manage analysts in your organization</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary">
          <Plus size={16} /> Add analyst
        </button>
      </div>

      {showAdd && (
        <div className="card p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Add Analyst</h2>
          {error && <p className="text-sm text-red-600 mb-3 whitespace-pre-line">{error}</p>}
          <form onSubmit={handleAdd} className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">First name</label>
              <input className="input" value={form.first_name} onChange={set('first_name')} required />
            </div>
            <div>
              <label className="label">Last name</label>
              <input className="input" value={form.last_name} onChange={set('last_name')} required />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" value={form.email} onChange={set('email')} required />
            </div>
            <div>
              <label className="label">Temporary password</label>
              <input type="password" className="input" value={form.password} onChange={set('password')} required minLength={8} />
            </div>
            <div className="col-span-2 flex gap-2">
              <button type="submit" className="btn-primary" disabled={adding}>{adding ? 'Adding…' : 'Add analyst'}</button>
              <button type="button" onClick={() => setShowAdd(false)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-gray-400">Loading…</div>
      ) : (
        <div className="card divide-y divide-gray-100">
          {members.map((m) => (
            <div key={m.id} className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-semibold text-sm">
                  {m.first_name?.[0] || m.email?.[0] || '?'}
                </div>
                <div>
                  <p className="font-medium text-gray-900">{m.first_name} {m.last_name}</p>
                  <p className="text-sm text-gray-500">{m.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
                  m.role === 'admin' ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  {m.role === 'admin' ? <Shield size={11} /> : <UserCheck size={11} />}
                  {m.role}
                </span>
                {!m.is_active && <span className="text-xs text-gray-400">Deactivated</span>}
                {m.role !== 'admin' && m.is_active && (
                  <button
                    onClick={() => handleRemove(m.id, `${m.first_name} ${m.last_name}`)}
                    className="p-1.5 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
