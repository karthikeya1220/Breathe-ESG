import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRecords, getSources } from '../api'
import {
  CheckCircle, Flag, XCircle, Clock, Filter,
  TrendingUp, Leaf, Zap, Plane, RefreshCw, ChevronRight
} from 'lucide-react'

const SCOPE_BADGE = {
  SCOPE_1: { label: 'Scope 1', cls: 'badge-scope1', icon: Leaf },
  SCOPE_2: { label: 'Scope 2', cls: 'badge-scope2', icon: Zap },
  SCOPE_3: { label: 'Scope 3', cls: 'badge-scope3', icon: Plane },
}

const STATUS_BADGE = {
  PENDING:  { label: 'Pending',  cls: 'badge-pending',  icon: Clock },
  APPROVED: { label: 'Approved', cls: 'badge-approved', icon: CheckCircle },
  FLAGGED:  { label: 'Flagged',  cls: 'badge-flagged',  icon: Flag },
  REJECTED: { label: 'Rejected', cls: 'badge-rejected', icon: XCircle },
}

function fmt(val, decimals = 1) {
  if (val == null) return '—'
  const n = parseFloat(val)
  if (n >= 1000) return `${(n / 1000).toFixed(decimals)}t`
  return `${n.toFixed(decimals)}`
}

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between mb-3">
        <span className="stat-label">{label}</span>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <div className="stat-value">{value}</div>
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [records, setRecords] = useState([])
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ status: '', scope: '', source: '' })
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const PAGE_SIZE = 50

  const fetchRecords = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) }
      const res = await getRecords(params)
      const data = res.data
      setRecords(data.results || data)
      setTotalCount(data.count || (data.results || data).length)
    } catch (_) {}
    setLoading(false)
  }, [filters, page])

  useEffect(() => { fetchRecords() }, [fetchRecords])
  useEffect(() => { getSources().then((r) => setSources(r.data.results || r.data)) }, [])

  // Stats derived from current page (approximate — full stats would need a separate API call)
  const pending  = records.filter((r) => r.review_status === 'PENDING').length
  const approved = records.filter((r) => r.review_status === 'APPROVED').length
  const flagged  = records.filter((r) => r.review_status === 'FLAGGED').length
  const totalCo2 = records.reduce((s, r) => s + (parseFloat(r.co2e_kg) || 0), 0)

  const setFilter = (key, val) => {
    setFilters((f) => ({ ...f, [key]: val }))
    setPage(1)
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Review Queue</h1>
          <p className="text-gray-400 text-sm mt-1">
            {totalCount} emission record{totalCount !== 1 ? 's' : ''} — approve, flag, or reject before audit lock
          </p>
        </div>
        <button onClick={fetchRecords} className="btn-ghost btn-sm" id="refresh-records-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Pending Review" value={pending}  icon={Clock}        color="text-yellow-400" />
        <StatCard label="Approved"       value={approved} icon={CheckCircle}  color="text-brand-400" />
        <StatCard label="Flagged"        value={flagged}  icon={Flag}         color="text-amber-400" />
        <StatCard
          label="Total CO₂e (shown)"
          value={`${fmt(totalCo2)} kg`}
          icon={TrendingUp}
          color="text-blue-400"
        />
      </div>

      {/* Filters */}
      <div className="card p-4 mb-4 flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-gray-400" />
        <span className="text-sm text-gray-400 font-medium">Filter:</span>

        <select
          id="status-filter"
          value={filters.status}
          onChange={(e) => setFilter('status', e.target.value)}
          className="input w-36 py-1.5 text-xs"
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="APPROVED">Approved</option>
          <option value="FLAGGED">Flagged</option>
          <option value="REJECTED">Rejected</option>
        </select>

        <select
          id="scope-filter"
          value={filters.scope}
          onChange={(e) => setFilter('scope', e.target.value)}
          className="input w-36 py-1.5 text-xs"
        >
          <option value="">All scopes</option>
          <option value="SCOPE_1">Scope 1</option>
          <option value="SCOPE_2">Scope 2</option>
          <option value="SCOPE_3">Scope 3</option>
        </select>

        <select
          id="source-filter"
          value={filters.source}
          onChange={(e) => setFilter('source', e.target.value)}
          className="input w-48 py-1.5 text-xs"
        >
          <option value="">All sources</option>
          {sources.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
        </select>

        {(filters.status || filters.scope || filters.source) && (
          <button
            onClick={() => setFilters({ status: '', scope: '', source: '' })}
            className="text-xs text-gray-400 hover:text-white transition-colors underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="skeleton h-12 rounded-xl" style={{ opacity: 1 - i * 0.1 }} />
          ))}
        </div>
      ) : records.length === 0 ? (
        <div className="card p-16 text-center">
          <Leaf className="w-10 h-10 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No records found</p>
          <p className="text-gray-600 text-sm mt-1">
            {Object.values(filters).some(Boolean)
              ? 'Try clearing your filters'
              : 'Upload a CSV to get started'}
          </p>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Activity</th>
                <th>Scope</th>
                <th>Period</th>
                <th>Quantity</th>
                <th className="text-right">CO₂e (kg)</th>
                <th>Source</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => {
                const scope  = SCOPE_BADGE[rec.scope]  || {}
                const status = STATUS_BADGE[rec.review_status] || {}
                const StatusIcon = status.icon || Clock
                return (
                  <tr
                    key={rec.id}
                    id={`record-row-${rec.id}`}
                    onClick={() => navigate(`/records/${rec.id}`)}
                  >
                    <td className="max-w-xs">
                      <div className="text-white font-medium truncate text-sm">
                        {rec.activity_description}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">{rec.category}</div>
                    </td>
                    <td>
                      {scope.cls && (
                        <span className={scope.cls}>
                          {scope.label}
                        </span>
                      )}
                    </td>
                    <td className="font-mono text-xs text-gray-400 whitespace-nowrap">
                      {rec.period_start}
                    </td>
                    <td className="font-mono text-xs text-gray-400">
                      {fmt(rec.raw_quantity, 0)} {rec.raw_unit}
                    </td>
                    <td className="text-right font-mono text-sm font-semibold text-white">
                      {rec.co2e_kg ? fmt(rec.co2e_kg) : <span className="text-gray-600">no factor</span>}
                    </td>
                    <td className="max-w-[140px]">
                      <div className="text-xs text-gray-400 truncate">{rec.source_name}</div>
                    </td>
                    <td>
                      <span className={status.cls}>
                        <StatusIcon className="w-3 h-3" />
                        {status.label}
                      </span>
                    </td>
                    <td>
                      <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-gray-400" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalCount > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-gray-400">
            Page {page} · {totalCount} total
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-ghost btn-sm"
            >← Prev</button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page * PAGE_SIZE >= totalCount}
              className="btn-ghost btn-sm"
            >Next →</button>
          </div>
        </div>
      )}
    </div>
  )
}
