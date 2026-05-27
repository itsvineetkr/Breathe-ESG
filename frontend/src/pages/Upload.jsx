import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadFile } from '../api/ingestion'
import Layout from '../components/Layout'
import { Upload as UploadIcon, FileText, AlertCircle, CheckCircle, Info } from 'lucide-react'

const SOURCE_TYPES = [
  {
    value: 'SAP',
    label: 'SAP Flat File',
    description: 'MB51 or ME2M export — fuel and procurement data. Supports German and English headers, semicolon/tab delimited.',
    accept: '.csv,.txt,.xlsx,.xls',
    example: 'sap_mb51_export.csv',
  },
  {
    value: 'UTILITY',
    label: 'Utility Portal CSV',
    description: 'Electricity usage export from utility portal (PG&E, National Grid, etc.). Billing period data with kWh/MWh usage.',
    accept: '.csv,.xlsx',
    example: 'utility_electricity.csv',
  },
  {
    value: 'TRAVEL',
    label: 'Travel Platform CSV',
    description: 'Navan, Concur, or similar export. Flights, hotels, and ground transport. Airport codes are used to calculate distances.',
    accept: '.csv,.xlsx',
    example: 'navan_travel_export.csv',
  },
]

export default function Upload() {
  const [sourceType, setSourceType] = useState('')
  const [datasetName, setDatasetName] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const fileRef = useRef()
  const navigate = useNavigate()

  const handleFile = (e) => {
    const f = e.target.files[0]
    if (f) {
      setFile(f)
      if (!datasetName) setDatasetName(f.name.replace(/\.[^/.]+$/, ''))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file || !sourceType || !datasetName) return
    setLoading(true)
    setError('')
    setResult(null)

    const fd = new FormData()
    fd.append('file', file)
    fd.append('source_type', sourceType)
    fd.append('name', datasetName)

    try {
      const res = await uploadFile(fd)
      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed.')
    } finally {
      setLoading(false)
    }
  }

  const stats = result?.stats

  return (
    <Layout>
      <div className="max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Upload Data</h1>
        <p className="text-gray-500 mb-6">Upload a dataset to begin ingestion and normalization.</p>

        {result ? (
          <div className="card p-8">
            <div className="flex items-center gap-3 mb-6">
              <CheckCircle className="text-green-500" size={28} />
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Upload complete</h2>
                <p className="text-gray-500 text-sm">{result.datasource.name}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Total rows', value: stats.total_rows },
                { label: 'Parsed', value: stats.parsed_rows, color: 'text-green-600' },
                { label: 'Flagged', value: stats.flagged_rows, color: stats.flagged_rows > 0 ? 'text-orange-600' : '' },
                { label: 'Failed', value: stats.failed_rows, color: stats.failed_rows > 0 ? 'text-red-600' : '' },
              ].map((s) => (
                <div key={s.label} className="bg-gray-50 rounded-lg p-4 text-center">
                  <p className={`text-2xl font-bold ${s.color || 'text-gray-900'}`}>{s.value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>

            {stats.flagged_rows > 0 && (
              <div className="flex items-start gap-2 p-3 bg-orange-50 border border-orange-200 rounded-lg text-sm text-orange-700 mb-4">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{stats.flagged_rows} rows were flagged for analyst review. These may have missing units, negative values, or unrecognized material types.</span>
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => navigate('/review')} className="btn-primary">
                Go to Review Queue
              </button>
              <button onClick={() => { setResult(null); setFile(null); setDatasetName(''); setSourceType('') }} className="btn-secondary">
                Upload Another
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Source type selection */}
            <div>
              <label className="label">Data source type</label>
              <div className="space-y-2">
                {SOURCE_TYPES.map((st) => (
                  <label
                    key={st.value}
                    className={`block border-2 rounded-xl p-4 cursor-pointer transition-colors ${
                      sourceType === st.value
                        ? 'border-brand-500 bg-brand-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <input
                      type="radio"
                      name="source_type"
                      value={st.value}
                      checked={sourceType === st.value}
                      onChange={() => setSourceType(st.value)}
                      className="sr-only"
                    />
                    <div className="flex items-start gap-3">
                      <div className={`w-4 h-4 rounded-full border-2 mt-0.5 shrink-0 ${
                        sourceType === st.value ? 'border-brand-500 bg-brand-500' : 'border-gray-300'
                      }`} />
                      <div>
                        <p className="font-medium text-gray-900">{st.label}</p>
                        <p className="text-sm text-gray-500 mt-0.5">{st.description}</p>
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Dataset name */}
            <div>
              <label className="label">Dataset name</label>
              <input
                className="input"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                required
                placeholder="e.g. SAP MB51 — Q1 2025 Fuel"
              />
            </div>

            {/* File upload */}
            <div>
              <label className="label">File</label>
              <div
                className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-brand-400 transition-colors"
                onClick={() => fileRef.current?.click()}
              >
                {file ? (
                  <div className="flex items-center justify-center gap-3">
                    <FileText className="text-brand-600" size={24} />
                    <div className="text-left">
                      <p className="font-medium text-gray-900">{file.name}</p>
                      <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <UploadIcon className="text-gray-400 mx-auto mb-2" size={32} />
                    <p className="text-gray-600 font-medium">Click to select file</p>
                    <p className="text-sm text-gray-400 mt-1">CSV, XLSX, or TXT — max 50 MB</p>
                  </>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept={SOURCE_TYPES.find((s) => s.value === sourceType)?.accept || '.csv,.xlsx,.txt'}
                className="hidden"
                onChange={handleFile}
              />
            </div>

            {sourceType && (
              <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
                <Info size={15} className="mt-0.5 shrink-0" />
                <span>
                  {sourceType === 'SAP' && 'Run report MB51 or ME2M in SAP → List → Export → Spreadsheet. German and English column headers are both supported.'}
                  {sourceType === 'UTILITY' && 'Download from your utility portal. Most utilities offer a "Download Data" or "Export" option in the billing or usage section.'}
                  {sourceType === 'TRAVEL' && 'From Navan: Reports → Trip Reports → Export. From Concur: Reporting → Standard Reports → Travel Detail Report → Export.'}
                </span>
              </div>
            )}

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={!file || !sourceType || !datasetName || loading}
            >
              {loading ? 'Uploading and parsing…' : 'Upload and Process'}
            </button>
          </form>
        )}
      </div>
    </Layout>
  )
}
