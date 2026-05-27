import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { register as registerApi } from '../api/auth'
import { Leaf } from 'lucide-react'

export default function Register() {
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', password: '', organization_name: ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await registerApi(form)
      login({ access: res.data.access, refresh: res.data.refresh }, res.data.user)
      navigate('/')
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        const msgs = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join('\n')
        setError(msgs)
      } else {
        setError('Registration failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Leaf className="text-brand-600" size={28} />
            <span className="text-2xl font-bold text-gray-900">Breathe ESG</span>
          </div>
          <p className="text-gray-600">Register your organization</p>
        </div>

        <div className="card p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-6">Create account</h1>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 whitespace-pre-line">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Organization name</label>
              <input className="input" value={form.organization_name} onChange={set('organization_name')} required placeholder="Acme Corp" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">First name</label>
                <input className="input" value={form.first_name} onChange={set('first_name')} required />
              </div>
              <div>
                <label className="label">Last name</label>
                <input className="input" value={form.last_name} onChange={set('last_name')} required />
              </div>
            </div>
            <div>
              <label className="label">Work email</label>
              <input type="email" className="input" value={form.email} onChange={set('email')} required placeholder="you@company.com" />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" className="input" value={form.password} onChange={set('password')} required minLength={8} placeholder="Min. 8 characters" />
            </div>
            <button type="submit" className="btn-primary w-full justify-center" disabled={loading}>
              {loading ? 'Creating account…' : 'Create organization'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-600">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-600 hover:text-brand-700 font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
