import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { updateOrg } from '../api/auth'
import { getMe } from '../api/auth'
import Layout from '../components/Layout'
import { Settings as SettingsIcon, Save, Info } from 'lucide-react'

export default function Settings() {
  const { user, setUser } = useAuth()
  const org = user?.organization || {}

  const [ef, setEf] = useState(org.electricity_emission_factor || 0.233)
  const [plantCodes, setPlantCodes] = useState(JSON.stringify(org.plant_code_map || {}, null, 2))
  const [fieldMappings, setFieldMappings] = useState(JSON.stringify(org.field_mapping_overrides || {}, null, 2))
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess(false)
    setSaving(true)
    try {
      let plant_code_map, field_mapping_overrides
      try { plant_code_map = JSON.parse(plantCodes) } catch { setError('Invalid JSON in plant code map.'); setSaving(false); return }
      try { field_mapping_overrides = JSON.parse(fieldMappings) } catch { setError('Invalid JSON in field mappings.'); setSaving(false); return }
      await updateOrg({ electricity_emission_factor: parseFloat(ef), plant_code_map, field_mapping_overrides })
      const me = await getMe()
      setUser(me.data)
      setSuccess(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Organization Settings</h1>
      <p className="text-gray-500 mb-6">{org.name}</p>

      <form onSubmit={handleSave} className="max-w-2xl space-y-6">
        {error && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}
        {success && <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">Settings saved.</div>}

        {/* Electricity emission factor */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-1">Electricity Emission Factor</h2>
          <p className="text-sm text-gray-500 mb-4">
            kg CO₂e per kWh. Defaults to the IEA 2023 world average (0.233). Set this to your grid's
            actual factor for accurate Scope 2 reporting. UK: 0.207, US avg: 0.386, EU avg: 0.233.
          </p>
          <div className="flex items-center gap-3">
            <input
              type="number"
              step="0.001"
              min="0"
              max="2"
              className="input w-36"
              value={ef}
              onChange={(e) => setEf(e.target.value)}
            />
            <span className="text-sm text-gray-500">kg CO₂e / kWh</span>
          </div>
        </div>

        {/* Plant code map */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-1">SAP Plant Code Map</h2>
          <p className="text-sm text-gray-500 mb-4">
            Map SAP plant codes to readable names. SAP exports contain codes like "WERK01" that are
            meaningless without this lookup. Format: {`{"WERK01": "Berlin Plant"}`}
          </p>
          <textarea
            className="input font-mono text-xs"
            rows={6}
            value={plantCodes}
            onChange={(e) => setPlantCodes(e.target.value)}
          />
        </div>

        {/* Field mapping overrides */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-1">Custom Field Mappings</h2>
          <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg text-sm text-blue-700 mb-4">
            <Info size={15} className="mt-0.5 shrink-0" />
            <span>
              If your SAP/Utility/Travel export uses non-standard column names, map them here.
              Format: {`{"SAP": {"MyQtyColumn": "quantity"}, "UTILITY": {"My kWh": "usage_kwh"}}`}
            </span>
          </div>
          <textarea
            className="input font-mono text-xs"
            rows={8}
            value={fieldMappings}
            onChange={(e) => setFieldMappings(e.target.value)}
          />
        </div>

        <button type="submit" className="btn-primary" disabled={saving}>
          <Save size={16} />
          {saving ? 'Saving…' : 'Save settings'}
        </button>
      </form>
    </Layout>
  )
}
