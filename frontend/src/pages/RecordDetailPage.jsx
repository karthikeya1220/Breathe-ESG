import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getRecord, reviewRecord } from '../api'
import {
  ArrowLeft, CheckCircle, Flag, XCircle, Lock,
  FileText, Clock, User, ChevronDown, ChevronUp,
  AlertTriangle, Leaf, Zap, Plane
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

function DataRow({ label, value, mono = false }) {
  return (
    <div className="flex justify-between items-start py-2 border-b border-surface-700 last:border-0">
      <span className="text-xs text-gray-400 font-medium w-44 flex-shrink-0">{label}</span>
      <span className={`text-sm text-gray-200 text-right flex-1 ml-4 ${mono ? 'font-mono' : ''}`}>
        {value ?? <span className="text-gray-600">—</span>}
      </span>
    </div>
  )
}

export default function RecordDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    getRecord(id)
      .then((r) => setRecord(r.data))
      .finally(() => setLoading(false))
  }, [id])

  const handleReview = async () => {
    if (!action) return
    setSubmitting(true)
    setSubmitError('')
    try {
      const res = await reviewRecord(id, action, comment)
      setRecord(res.data)
      setAction('')
      setComment('')
    } catch (err) {
      setSubmitError(err.response?.data?.error || err.response?.data?.non_field_errors?.[0] || 'Action failed.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return (
    <div className="p-8 space-y-4">
      {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-10 rounded-xl" />)}
    </div>
  )

  if (!record) return (
    <div className="p-8 text-center text-gray-400">Record not found.</div>
  )

  const scope  = SCOPE_BADGE[record.scope]  || {}
  const status = STATUS_BADGE[record.review_status] || {}
  const StatusIcon = status.icon || Clock
  const ScopeIcon  = scope.icon  || Leaf

  const requiresComment = ['FLAGGED', 'REJECTED'].includes(action)
  const canSubmit = action && (!requiresComment || comment.trim())

  return (
    <div className="p-8 max-w-4xl mx-auto animate-fade-in">
      {/* Back nav */}
      <button
        id="back-to-dashboard"
        onClick={() => navigate('/dashboard')}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to Review Queue
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap mb-2">
            <span className={scope.cls}>
              <ScopeIcon className="w-3 h-3" />
              {scope.label}
            </span>
            <span className={status.cls}>
              <StatusIcon className="w-3 h-3" />
              {status.label}
            </span>
            {record.is_locked && (
              <span className="badge bg-surface-700 text-gray-400 border border-surface-500">
                <Lock className="w-3 h-3" />
                Locked
              </span>
            )}
          </div>
          <h1 className="text-xl font-bold text-white">{record.activity_description}</h1>
          <p className="text-gray-400 text-sm mt-1">{record.category}</p>
        </div>
        {record.co2e_kg && (
          <div className="card px-5 py-3 text-center flex-shrink-0">
            <div className="text-2xl font-bold text-white">{parseFloat(record.co2e_kg).toFixed(1)}</div>
            <div className="text-xs text-gray-400 mt-0.5">kg CO₂e</div>
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Left — normalized record */}
        <div className="space-y-4">
          <div className="card p-5">
            <h2 className="section-title mb-4 flex items-center gap-2">
              <Leaf className="w-4 h-4 text-brand-400" />
              Normalized Record
            </h2>
            <DataRow label="Period start" value={record.period_start} mono />
            <DataRow label="Period end" value={record.period_end} mono />
            <DataRow label="Raw quantity" value={`${parseFloat(record.raw_quantity).toFixed(3)} ${record.raw_unit}`} mono />
            <DataRow label="Normalized quantity" value={`${parseFloat(record.quantity_normalized).toFixed(3)} ${record.unit_normalized}`} mono />
            <DataRow label="CO₂e" value={record.co2e_kg ? `${parseFloat(record.co2e_kg).toFixed(4)} kg` : null} mono />
            <DataRow label="Source" value={record.source_name} />
            <DataRow label="Created" value={new Date(record.created_at).toLocaleString()} />
            {record.is_locked && (
              <DataRow label="Locked at" value={new Date(record.locked_at).toLocaleString()} />
            )}
          </div>

          {/* Emission factor */}
          {record.emission_factor_detail && (
            <div className="card p-5">
              <h2 className="section-title mb-4">Emission Factor</h2>
              <DataRow label="Source" value={record.emission_factor_detail.source} />
              <DataRow label="Activity" value={record.emission_factor_detail.activity} mono />
              <DataRow label="Factor" value={`${record.emission_factor_detail.factor_kg_co2e} kg CO₂e/${record.emission_factor_detail.unit}`} mono />
            </div>
          )}
          {!record.emission_factor_detail && (
            <div className="card p-4 border-amber-900/50 bg-amber-950/20">
              <div className="flex items-center gap-2 text-amber-400 text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>No emission factor matched — CO₂e not computed</span>
              </div>
            </div>
          )}

          {/* Review history */}
          {record.reviews?.length > 0 && (
            <div className="card p-5">
              <h2 className="section-title mb-4">Review History</h2>
              <div className="space-y-3">
                {record.reviews.map((rev) => {
                  const s = STATUS_BADGE[rev.action] || {}
                  const RIcon = s.icon || Clock
                  return (
                    <div key={rev.id} className="flex items-start gap-3">
                      <div className={`mt-0.5 ${s.cls} p-1 rounded`}>
                        <RIcon className="w-3 h-3" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-white font-medium">{rev.action}</span>
                          <span className="text-xs text-gray-500">by {rev.reviewer_username}</span>
                        </div>
                        {rev.comment && (
                          <p className="text-xs text-gray-400 mt-1 italic">"{rev.comment}"</p>
                        )}
                        <p className="text-xs text-gray-600 mt-0.5">
                          {new Date(rev.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right — raw record + review panel */}
        <div className="space-y-4">
          {/* Raw record */}
          {record.raw_record && (
            <div className="card p-5">
              <button
                onClick={() => setShowRaw(!showRaw)}
                className="flex items-center justify-between w-full"
              >
                <h2 className="section-title flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-400" />
                  Raw Source Data
                  <span className="text-xs font-normal text-gray-500">Row {record.raw_record.row_number}</span>
                </h2>
                {showRaw ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
              </button>
              {showRaw && (
                <div className="mt-4 animate-fade-in">
                  <div className="bg-surface-900 border border-surface-700 rounded-lg p-4 overflow-x-auto">
                    <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {JSON.stringify(record.raw_record.raw_data, null, 2)}
                    </pre>
                  </div>
                  {record.raw_record.parse_errors?.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {record.raw_record.parse_errors.map((e, i) => (
                        <div key={i} className="text-xs text-red-400 flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> {e}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Review actions */}
          <div className={`card p-5 ${record.is_locked ? 'opacity-60' : ''}`}>
            <h2 className="section-title mb-4 flex items-center gap-2">
              <User className="w-4 h-4 text-gray-400" />
              Analyst Action
              {record.is_locked && <Lock className="w-3.5 h-3.5 text-gray-500" />}
            </h2>

            {record.is_locked ? (
              <div className="text-sm text-gray-400 flex items-center gap-2">
                <Lock className="w-4 h-4" />
                This record is locked after approval and cannot be modified.
              </div>
            ) : (
              <>
                <div className="grid grid-cols-3 gap-2 mb-4">
                  {[
                    { val: 'APPROVED', label: 'Approve', cls: 'btn-success', icon: CheckCircle },
                    { val: 'FLAGGED',  label: 'Flag',    cls: 'btn-warning', icon: Flag },
                    { val: 'REJECTED', label: 'Reject',  cls: 'btn-danger',  icon: XCircle },
                  ].map(({ val, label, cls, icon: Icon }) => (
                    <button
                      key={val}
                      id={`action-${val.toLowerCase()}`}
                      onClick={() => setAction(action === val ? '' : val)}
                      className={`${cls} justify-center ${action === val ? 'ring-2 ring-offset-1 ring-offset-surface-800' : ''}`}
                    >
                      <Icon className="w-4 h-4" />
                      {label}
                    </button>
                  ))}
                </div>

                {action && (
                  <div className="animate-slide-up space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1.5" htmlFor="review-comment">
                        Comment {requiresComment ? <span className="text-red-400">*required</span> : '(optional)'}
                      </label>
                      <textarea
                        id="review-comment"
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder={
                          action === 'FLAGGED'  ? 'Describe what looks suspicious…' :
                          action === 'REJECTED' ? 'Reason for rejection…' :
                          'Add a note (optional)…'
                        }
                        rows={3}
                        className="input resize-none"
                      />
                    </div>

                    {submitError && (
                      <div className="text-xs text-red-400 flex items-center gap-1">
                        <XCircle className="w-3 h-3" /> {submitError}
                      </div>
                    )}

                    <button
                      id="submit-review-btn"
                      onClick={handleReview}
                      disabled={!canSubmit || submitting}
                      className={`w-full justify-center ${
                        action === 'APPROVED' ? 'btn-success' :
                        action === 'FLAGGED'  ? 'btn-warning' :
                        'btn-danger'
                      }`}
                    >
                      {submitting ? (
                        <div className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                      ) : (
                        <>
                          {action === 'APPROVED' && <CheckCircle className="w-4 h-4" />}
                          {action === 'FLAGGED'  && <Flag       className="w-4 h-4" />}
                          {action === 'REJECTED' && <XCircle    className="w-4 h-4" />}
                          Confirm {action.toLowerCase()}
                        </>
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
