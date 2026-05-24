import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { getSources, uploadFile } from '../api'
import {
  Upload, FileText, CheckCircle, XCircle,
  AlertTriangle, ChevronRight, X, Loader2
} from 'lucide-react'

const SOURCE_TYPE_LABELS = {
  SAP_FLAT_FILE: 'SAP Flat File',
  UTILITY_CSV: 'Utility CSV',
  TRAVEL_CSV: 'Travel CSV',
}

const SCOPE_LABELS = {
  SCOPE_1: { label: 'Scope 1', cls: 'badge-scope1' },
  SCOPE_2: { label: 'Scope 2', cls: 'badge-scope2' },
  SCOPE_3: { label: 'Scope 3', cls: 'badge-scope3' },
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [sources, setSources] = useState([])
  const [selectedSource, setSelectedSource] = useState('')
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getSources().then((r) => setSources(r.data.results || r.data))
  }, [])

  const onDrop = useCallback((accepted) => {
    if (accepted.length) {
      setFile(accepted[0])
      setResult(null)
      setError('')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.txt'] },
    maxFiles: 1,
  })

  const handleUpload = async () => {
    if (!file || !selectedSource) return
    setUploading(true)
    setProgress(0)
    setError('')
    setResult(null)
    try {
      const res = await uploadFile(file, selectedSource, setProgress)
      setResult(res.data)
    } catch (err) {
      if (err.response?.status === 409) {
        setError(`Duplicate file: ${err.response.data.error}`)
      } else {
        setError(err.response?.data?.error || 'Upload failed. Please try again.')
      }
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setResult(null)
    setError('')
    setProgress(0)
  }

  return (
    <div className="p-8 max-w-2xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Upload Emissions Data</h1>
        <p className="text-gray-400 text-sm mt-1">
          Upload a CSV from SAP, a utility portal, or your corporate travel platform.
        </p>
      </div>

      {/* Step 1: Select source */}
      <div className="card p-6 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-full bg-brand-700 flex items-center justify-center text-xs font-bold text-brand-200">1</div>
          <h2 className="font-semibold text-white text-sm">Select Data Source</h2>
        </div>
        <div className="grid gap-2">
          {sources.map((src) => {
            const scope = SCOPE_LABELS[src.scope] || {}
            const isSelected = selectedSource === src.id
            return (
              <button
                key={src.id}
                id={`source-${src.id}`}
                onClick={() => setSelectedSource(src.id)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-all
                  ${isSelected
                    ? 'border-brand-600 bg-brand-900/30 text-white'
                    : 'border-surface-600 bg-surface-700 text-gray-300 hover:border-surface-500 hover:bg-surface-600'}`}
              >
                <FileText className="w-4 h-4 flex-shrink-0 text-gray-400" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{src.display_name}</div>
                  <div className="text-xs text-gray-500">{SOURCE_TYPE_LABELS[src.source_type] || src.source_type}</div>
                </div>
                <span className={scope.cls}>{scope.label}</span>
              </button>
            )
          })}
          {sources.length === 0 && (
            <div className="text-center py-6 text-gray-500 text-sm">No data sources configured.</div>
          )}
        </div>
      </div>

      {/* Step 2: Drop file */}
      <div className="card p-6 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-full bg-brand-700 flex items-center justify-center text-xs font-bold text-brand-200">2</div>
          <h2 className="font-semibold text-white text-sm">Drop Your CSV File</h2>
        </div>

        {file ? (
          <div className="flex items-center gap-3 bg-surface-700 border border-surface-500 rounded-lg px-4 py-3">
            <FileText className="w-5 h-5 text-brand-400 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">{file.name}</div>
              <div className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</div>
            </div>
            <button onClick={reset} className="text-gray-400 hover:text-white transition-colors p-1">
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all
              ${isDragActive
                ? 'border-brand-500 bg-brand-900/20'
                : 'border-surface-600 hover:border-surface-400 hover:bg-surface-800'}`}
          >
            <input {...getInputProps()} id="file-dropzone" />
            <Upload className={`w-10 h-10 mx-auto mb-3 transition-colors ${isDragActive ? 'text-brand-400' : 'text-gray-500'}`} />
            <p className="text-sm font-medium text-gray-300">
              {isDragActive ? 'Drop it here!' : 'Drag & drop your CSV here'}
            </p>
            <p className="text-xs text-gray-500 mt-1">or click to browse — .csv and .txt accepted</p>
          </div>
        )}
      </div>

      {/* Upload button + progress */}
      {uploading && (
        <div className="card p-4 mb-4">
          <div className="flex items-center gap-3 mb-2">
            <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
            <span className="text-sm text-gray-300">Uploading and parsing…</span>
            <span className="ml-auto text-sm font-mono text-brand-400">{progress}%</span>
          </div>
          <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 bg-red-950/40 border border-red-900 rounded-xl p-4 mb-4 animate-fade-in">
          <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Result card */}
      {result && (
        <div className="card p-6 mb-4 animate-slide-up">
          <div className="flex items-center gap-3 mb-4">
            {result.row_count_failed === 0
              ? <CheckCircle className="w-5 h-5 text-brand-400" />
              : <AlertTriangle className="w-5 h-5 text-amber-400" />}
            <span className="font-semibold text-white">
              {result.row_count_failed === 0 ? 'Upload complete!' : 'Uploaded with some errors'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-surface-700 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-white">{result.row_count_raw}</div>
              <div className="text-xs text-gray-400 mt-0.5">Total rows</div>
            </div>
            <div className="bg-surface-700 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-brand-400">{result.row_count_ok}</div>
              <div className="text-xs text-gray-400 mt-0.5">Records created</div>
            </div>
            <div className="bg-surface-700 rounded-lg p-3 text-center">
              <div className={`text-xl font-bold ${result.row_count_failed > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                {result.row_count_failed}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">Parse errors</div>
            </div>
          </div>

          {result.error_summary?.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Parse errors</div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {result.error_summary.map((e, i) => (
                  <div key={i} className="flex gap-2 text-xs bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">
                    <span className="text-red-500 font-mono">Row {e.row}</span>
                    <span className="text-red-300">{e.errors?.join(', ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={() => navigate('/dashboard')} className="btn-primary flex-1 justify-center">
              Review records
              <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={reset} className="btn-ghost">Upload another</button>
          </div>
        </div>
      )}

      {!uploading && !result && (
        <button
          id="upload-submit-btn"
          onClick={handleUpload}
          disabled={!file || !selectedSource}
          className="btn-primary btn-lg w-full justify-center"
        >
          <Upload className="w-4 h-4" />
          Upload and Parse
        </button>
      )}
    </div>
  )
}
