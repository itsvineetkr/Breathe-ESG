import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { login as loginApi } from '../api/auth'
import { Leaf } from 'lucide-react'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await loginApi(email, password)
      login({ access: res.data.access, refresh: res.data.refresh }, res.data.user)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Check your credentials.')
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
          <p className="text-gray-600">Data Ingestion Platform</p>
        </div>

        <div className="card p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-6">Sign in</h1>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
              />
            </div>
            <button type="submit" className="btn-primary w-full justify-center" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-600">
            New organization?{' '}
            <Link to="/register" className="text-brand-600 hover:text-brand-700 font-medium">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
