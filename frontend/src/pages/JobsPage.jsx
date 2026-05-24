import { useState, useEffect } from 'react'
import { getJobs } from '../api'
import {
  Briefcase, CheckCircle, XCircle, Clock, Loader2,
  ChevronDown, ChevronUp, AlertTriangle
} from 'lucide-react'

const STATUS_STYLES = {
  COMPLETED:  { cls: 'badge-approved', icon: CheckCircle },
  FAILED:     { cls: 'badge-rejected', icon: XCircle },
  PENDING:    { cls: 'badge-pending',  icon: Clock },
  PROCESSING: { cls: 'badge-pending',  icon: Loader2 },
}

function JobRow({ job }) {
  const [expanded, setExpanded] = useState(false)
  const s = STATUS_STYLES[job.status] || {}
  const Icon = s.icon || Clock

  const pct = job.row_count_raw > 0
    ? Math.round((job.row_count_ok / job.row_count_raw) * 100)
    : 0

  return (
    <div className="card overflow-hidden mb-3 transition-all">
      <button
        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-surface-700/30 transition-colors text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap mb-1">
            <span className="text-sm font-semibold text-white truncate">
              {job.data_source_name}
            </span>
            <span className={`${s.cls} badge`}>
              <Icon className={`w-3 h-3 ${job.status === 'PROCESSING' ? 'animate-spin' : ''}`} />
              {job.status}
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400 flex-wrap">
            <span>{job.original_filename || 'Unknown file'}</span>
            <span>{job.source_type}</span>
            {job.started_at && (
              <span>{new Date(job.started_at).toLocaleString()}</span>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex-shrink-0 w-32 hidden sm:block">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>{job.row_count_ok} ok</span>
            <span>{job.row_count_raw} total</span>
          </div>
          <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${job.row_count_failed > 0 ? 'bg-amber-500' : 'bg-brand-500'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0 ml-2">
          {job.row_count_failed > 0 && (
            <div className="flex items-center gap-1 text-xs text-red-400">
              <AlertTriangle className="w-3.5 h-3.5" />
              {job.row_count_failed} errors
            </div>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 border-t border-surface-700 animate-fade-in">
          <div className="grid grid-cols-3 gap-3 mt-4 mb-4">
            <div className="bg-surface-700 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-white">{job.row_count_raw}</div>
              <div className="text-xs text-gray-400">Raw rows</div>
            </div>
            <div className="bg-surface-700 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-brand-400">{job.row_count_ok}</div>
              <div className="text-xs text-gray-400">Records created</div>
            </div>
            <div className="bg-surface-700 rounded-lg p-3 text-center">
              <div className={`text-lg font-bold ${job.row_count_failed > 0 ? 'text-red-400' : 'text-gray-500'}`}>
                {job.row_count_failed}
              </div>
              <div className="text-xs text-gray-400">Parse errors</div>
            </div>
          </div>

          {job.error_summary?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Parse errors
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {job.error_summary.map((e, i) => (
                  <div key={i} className="flex gap-3 text-xs bg-red-950/20 border border-red-900/40 rounded-lg px-3 py-2">
                    <span className="text-red-500 font-mono flex-shrink-0">Row {e.row}</span>
                    <span className="text-red-300">{Array.isArray(e.errors) ? e.errors.join(', ') : e.errors}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {job.error_summary?.length === 0 && (
            <div className="flex items-center gap-2 text-sm text-brand-400">
              <CheckCircle className="w-4 h-4" />
              All rows parsed successfully
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function JobsPage() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getJobs()
      .then((r) => setJobs(r.data.results || r.data))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Ingestion Jobs</h1>
        <p className="text-gray-400 text-sm mt-1">
          History of all CSV uploads — click to see per-row parse errors
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-16 rounded-xl" />)}
        </div>
      ) : jobs.length === 0 ? (
        <div className="card p-16 text-center">
          <Briefcase className="w-10 h-10 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No ingestion jobs yet</p>
          <p className="text-gray-600 text-sm mt-1">Upload a CSV to create your first job</p>
        </div>
      ) : (
        <div>
          {jobs.map((job) => <JobRow key={job.id} job={job} />)}
        </div>
      )}
    </div>
  )
}
