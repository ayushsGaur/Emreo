import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { useStore } from '../../store/useStore.jsx'
import { incidentsApi } from '../../services/api.js'
import { Spinner } from '../ui/primitives.jsx'

export default function IncidentForm() {
  const { state, dispatch } = useStore()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    caller_name: '', caller_phone: '', complaint: '',
    address: '', patient_age: '', patient_conscious: '', patient_breathing: '',
  })

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

//   const handleSubmit = async (e) => {
//     e.preventDefault()
//     setLoading(true)
//     try {
//       const payload = {
//         caller_name:  form.caller_name,
//         caller_phone: form.caller_phone,
//         complaint:    form.complaint,
//         address:      form.address || undefined,
//         patient_age:  form.patient_age ? +form.patient_age : undefined,
//         patient_conscious: form.patient_conscious === '' ? undefined : form.patient_conscious === 'true',
//         patient_breathing: form.patient_breathing === '' ? undefined : form.patient_breathing === 'true',
//       }
//       const payload = {
//   caller_name:  form.caller_name,
//   caller_phone: form.caller_phone,
//   complaint:    form.complaint,
//   address:      form.address || undefined,

//   latitude: 30.9,       // ✅ TEMP FIX
//   longitude: 75.85,     // ✅ TEMP FIX

//   patient_age:  form.patient_age ? +form.patient_age : undefined,
//   patient_conscious: form.patient_conscious === '' ? undefined : form.patient_conscious === 'true',
//   patient_breathing: form.patient_breathing === '' ? undefined : form.patient_breathing === 'true',
// }
//       const inc = await incidentsApi.create(payload)
//       dispatch({ type: 'ADD_INCIDENT', payload: inc })
//       dispatch({ type: 'TOGGLE_FORM', payload: false })
//       toast.success(`Incident logged · ${inc.severity || 'Triaging…'} · #${inc.id.slice(0,8).toUpperCase()}`, { icon: '⚡' })
//       setForm({ caller_name:'',caller_phone:'',complaint:'',address:'',patient_age:'',patient_conscious:'',patient_breathing:'' })
      
//     } catch (err) {
//       toast.error(err.message || 'Failed to log incident')
//     } finally {
//       setLoading(false)
//     }
//   }

  const handleSubmit = async (e) => {
  e.preventDefault()
  setLoading(true)

  try {
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const payload = {
        caller_name: form.caller_name,
        caller_phone: form.caller_phone,
        complaint: form.complaint,
        address: form.address || undefined,

        // ✅ AUTO GPS
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,

        patient_age: form.patient_age ? +form.patient_age : undefined,
        patient_conscious:
          form.patient_conscious === ''
            ? undefined
            : form.patient_conscious === 'true',
        patient_breathing:
          form.patient_breathing === ''
            ? undefined
            : form.patient_breathing === 'true',
      }

      const inc = await incidentsApi.create(payload)

      dispatch({ type: 'ADD_INCIDENT', payload: inc })
      dispatch({ type: 'TOGGLE_FORM', payload: false })

      toast.success(
        `Incident logged · ${inc.severity || 'Triaging…'} · #${inc.id
          .slice(0, 8)
          .toUpperCase()}`,
        { icon: '⚡' }
      )

      setForm({
        caller_name: '',
        caller_phone: '',
        complaint: '',
        address: '',
        patient_age: '',
        patient_conscious: '',
        patient_breathing: '',
      })

      setLoading(false)
    },
    (err) => {
      toast.error("Location access denied ❌")
      setLoading(false)
    })

  } catch (err) {
    toast.error(err.message || 'Failed to log incident')
    setLoading(false)
  }
}

  if (!state.showForm) return null

  return (
    <div
      onClick={() => dispatch({ type: 'TOGGLE_FORM', payload: false })}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.72)', backdropFilter: 'blur(6px)', zIndex: 5000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
    >
      <motion.div
        initial={{ opacity: 0, scale: .95, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: .95 }}
        transition={{ duration: .2 }}
        onClick={e => e.stopPropagation()}
        style={{ background: 'var(--bg-1)', border: '1px solid var(--b-2)', borderRadius: 'var(--r-xl)', width: '100%', maxWidth: 500, overflow: 'hidden', boxShadow: '0 24px 80px rgba(0,0,0,.6)' }}
      >
        {/* Header */}
        <div style={{ padding: '15px 20px', borderBottom: '1px solid var(--b-1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--red)', marginBottom: 3 }}>⚡ Emergency Intake</div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 17 }}>Log New Incident</div>
          </div>
          <button onClick={() => dispatch({ type: 'TOGGLE_FORM', payload: false })} style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-3)', border: '1px solid var(--b-2)', color: 'var(--text-2)', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 13 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Field label="Caller name *"><input value={form.caller_name} onChange={set('caller_name')} required placeholder="Full name" /></Field>
            <Field label="Phone *"><input value={form.caller_phone} onChange={set('caller_phone')} required placeholder="+91 XXXXX XXXXX" /></Field>
          </div>

          <Field label="Complaint *">
            <textarea rows={3} value={form.complaint} onChange={set('complaint')} required placeholder="Describe the emergency in detail…" style={{ resize: 'vertical' }} />
          </Field>

          <Field label="Location / address *">
            <input value={form.address} onChange={set('address')} required placeholder="Street, area, landmark…" />
          </Field>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <Field label="Patient age">
              <input type="number" value={form.patient_age} onChange={set('patient_age')} placeholder="Years" min="0" max="130" />
            </Field>
            <Field label="Conscious?">
              <select value={form.patient_conscious} onChange={set('patient_conscious')}>
                <option value="">Unknown</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </Field>
            <Field label="Breathing?">
              <select value={form.patient_breathing} onChange={set('patient_breathing')}>
                <option value="">Unknown</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </Field>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button type="button" onClick={() => dispatch({ type: 'TOGGLE_FORM', payload: false })} style={{
              flex: 1, padding: '10px', background: 'var(--bg-3)', border: '1px solid var(--b-2)',
              borderRadius: 'var(--r-md)', color: 'var(--text-2)',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, letterSpacing: '.06em',
            }}>Cancel</button>

            <button type="submit" disabled={loading} style={{
              flex: 2, padding: '10px', background: loading ? 'var(--bg-3)' : 'var(--red)',
              border: 'none', borderRadius: 'var(--r-md)', color: loading ? 'var(--text-3)' : '#fff',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, letterSpacing: '.06em',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : '0 0 18px rgba(255,61,61,.3)',
            }}>
              {loading && <Spinner size={13} color="#fff" />}
              {loading ? 'Logging…' : '⚡ Log Incident'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--text-3)' }}>{label}</span>
      {children}
    </label>
  )
}
