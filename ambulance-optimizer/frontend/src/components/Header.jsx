import { useStore } from '../store/useStore.jsx'
import { Btn } from './ui/primitives.jsx'

export default function Header({ wsStatus, onNewIncident, onTogglePanel, panelVisible }) {
  const { state } = useStore()

  const incidents   = state.incidents
  const ambulances  = Object.values(state.ambulances)
  const activeCount = incidents.filter(i => i.status !== 'closed').length
  const p1Count     = incidents.filter(i => i.severity === 'P1' && i.status !== 'closed').length
  const availCount  = ambulances.filter(a => a.status === 'available').length
  const avgEta      = state.summary?.performance?.avg_response_time_minutes

  const wsColor = { open: 'var(--green)', connecting: 'var(--yellow)', closed: 'var(--text-3)', error: 'var(--red)' }[wsStatus] || 'var(--text-3)'
  const wsText  = { open: 'LIVE', connecting: 'CONNECTING', closed: 'OFFLINE', error: 'ERROR' }[wsStatus] || '—'

  return (
    <header style={{
      height: 58, display: 'flex', alignItems: 'center',
      padding: '0 20px', gap: 20,
      background: 'var(--bg-1)', borderBottom: '1px solid var(--b-1)',
      flexShrink: 0, zIndex: 100, position: 'relative',
    }}>

      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginRight: 6, flexShrink: 0 }}>
        <div style={{
          width: 34, height: 34, background: 'var(--red)', borderRadius: 9,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
          boxShadow: '0 0 18px rgba(255,61,61,.45)', flexShrink: 0,
        }}>🚑</div>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 15, letterSpacing: '.02em', lineHeight: 1 }}>RESPONSE</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.14em', color: 'var(--text-3)', textTransform: 'uppercase', marginTop: 2 }}>Dispatch Optimizer</div>
        </div>
      </div>

      {/* KPI strip */}
      <div style={{ display: 'flex', gap: 0, flex: 1 }}>
        {[
          { val: activeCount,                                      color: 'var(--text-1)', label: 'Active' },
          { val: p1Count,                                          color: p1Count > 0 ? 'var(--red)' : 'var(--text-3)', label: 'Critical P1' },
          { val: availCount,                                       color: 'var(--green)', label: 'Available' },
          { val: avgEta ? `${Math.round(avgEta)}m` : '—',         color: 'var(--blue)', label: 'Avg ETA' },
          { val: state.summary?.incidents?.active_total ?? '—',   color: 'var(--text-2)', label: 'Today' },
        ].map(({ val, color, label }) => (
          <div key={label} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '0 18px', borderRight: '1px solid var(--b-1)',
          }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{val}</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.1em', color: 'var(--text-3)', textTransform: 'uppercase', marginTop: 2 }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Right controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginLeft: 'auto' }}>
        {/* WS status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span
            className={wsStatus !== 'open' ? 'blink' : ''}
            style={{ width: 7, height: 7, borderRadius: '50%', background: wsColor, display: 'inline-block' }}
          />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.1em', color: 'var(--text-3)', textTransform: 'uppercase' }}>{wsText}</span>
        </div>

        <Btn variant={panelVisible ? 'active' : 'ghost'} onClick={onTogglePanel}>ML Panel</Btn>
        <Btn variant="primary" onClick={onNewIncident}>+ New Incident</Btn>
      </div>
    </header>
  )
}
