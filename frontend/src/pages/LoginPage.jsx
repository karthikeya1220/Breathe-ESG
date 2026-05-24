import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Leaf, Eye, EyeOff, AlertCircle } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.non_field_errors?.[0] || 'Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-950 flex">
      {/* Left — branding panel */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 bg-surface-900 border-r border-surface-700 p-12">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white">Breathe ESG</span>
        </div>

        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 bg-brand-900/40 border border-brand-800/50 rounded-full px-4 py-1.5">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
            <span className="text-xs text-brand-300 font-medium">Emissions Ingestion Platform</span>
          </div>
          <h1 className="text-4xl font-bold text-white leading-tight">
            Ingest. Normalize.<br />
            <span className="text-brand-400">Sign off.</span>
          </h1>
          <p className="text-gray-400 text-lg leading-relaxed">
            Enterprise emissions data from SAP, utility portals, and corporate travel — 
            normalized, reviewed, and locked for audit.
          </p>

          <div className="grid grid-cols-3 gap-4 pt-4">
            {[
              { label: 'Scope 1', sub: 'Fuel combustion', color: 'text-orange-400', bg: 'bg-orange-950 border-orange-900' },
              { label: 'Scope 2', sub: 'Electricity', color: 'text-blue-400', bg: 'bg-blue-950 border-blue-900' },
              { label: 'Scope 3', sub: 'Travel & more', color: 'text-purple-400', bg: 'bg-purple-950 border-purple-900' },
            ].map(({ label, sub, color, bg }) => (
              <div key={label} className={`${bg} border rounded-xl p-4`}>
                <div className={`text-sm font-bold ${color}`}>{label}</div>
                <div className="text-xs text-gray-400 mt-1">{sub}</div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-gray-600">
          DEFRA 2024 · EPA eGRID 2023 · GHG Protocol aligned
        </p>
      </div>

      {/* Right — login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm animate-fade-in">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center">
              <Leaf className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold text-white">Breathe ESG</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white">Welcome back</h2>
            <p className="text-gray-400 text-sm mt-1">Sign in to your analyst account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5" htmlFor="username-input">
                Username
              </label>
              <input
                id="username-input"
                type="text"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                placeholder="analyst"
                className="input"
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5" htmlFor="password-input">
                Password
              </label>
              <div className="relative">
                <input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="••••••••"
                  className="input pr-10"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 transition-colors"
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-red-950/50 border border-red-900 rounded-lg px-3 py-2.5 text-sm text-red-300 animate-fade-in">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              id="login-submit-btn"
              type="submit"
              disabled={loading}
              className="btn-primary btn-lg w-full justify-center mt-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in…
                </>
              ) : 'Sign in'}
            </button>
          </form>

          <div className="mt-8 p-4 bg-surface-800 border border-surface-600 rounded-xl">
            <div className="text-xs text-gray-400 font-medium mb-2">Demo credentials</div>
            <div className="font-mono text-xs text-gray-300 space-y-1">
              <div><span className="text-gray-500">user:</span> analyst</div>
              <div><span className="text-gray-500">pass:</span> demo1234</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
